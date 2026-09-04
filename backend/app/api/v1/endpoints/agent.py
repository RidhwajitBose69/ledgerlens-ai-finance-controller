import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from backend.app.db.mongo import db_container
from backend.app.agents.agent import FinanceControllerAgent

router = APIRouter(prefix="/exceptions", tags=["AI Investigation & Resolution"])
agent_instance = FinanceControllerAgent()

@router.post("/{exception_id}/investigate", response_model=Dict[str, Any])
async def run_ai_investigation(
    exception_id: str,
    provider: Optional[str] = Query(None, description="MOCK, OPENAI, GEMINI"),
    force: bool = Query(False, description="Force rerun of AI investigation")
):
    try:
        res = await agent_instance.investigate_exception(exception_id, provider, force)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Fallback handling on agent failure (Rule 108)
        exp = await db_container.db.exceptions.find_one({"exception_id": exception_id})
        if exp:
            tx_id = exp.get("transaction_id")
            await db_container.db.exceptions.update_one(
                {"exception_id": exception_id},
                {"$set": {"status": "HUMAN_REVIEW", "recommended_action": "AI_FAILURE_FALLBACK_HUMAN_REVIEW"}}
            )
            import hashlib
            import json
            last_hash = await db_container.db.audit_logs.find_one(sort=[("timestamp", -1)])
            previous_hash = last_hash.get("event_hash") if last_hash else None

            audit_id = f"AUD_{uuid.uuid4().hex[:12]}"
            payload = {
                "audit_id": audit_id,
                "run_id": exp.get("run_id"),
                "transaction_id": tx_id,
                "actor_type": "SYSTEM",
                "actor_id": "fallback_handler",
                "action": "AI_INVESTIGATION_FAILED",
                "previous_state": exp.get("status"),
                "new_state": "HUMAN_REVIEW",
                "reason": f"AI investigation encountered error: {str(e)}",
                "evidence": {"error": str(e)},
                "confidence": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"exception_id": exception_id},
                "previous_hash": previous_hash
            }
            canonical_payload = json.dumps(payload, sort_keys=True)
            event_hash = hashlib.sha256((str(previous_hash) + canonical_payload).encode()).hexdigest()
            payload["event_hash"] = event_hash
            payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
            await db_container.db.audit_logs.insert_one(payload)
        raise HTTPException(status_code=500, detail=f"AI Investigation failed. Exception escalated to HUMAN_REVIEW: {str(e)}")

@router.post("/{exception_id}/resolve", response_model=Dict[str, Any])
async def resolve_exception_human(
    exception_id: str,
    payload: Dict[str, Any]
):
    action = payload.get("action", "approve")  # approve, reject, resolve, mark_unresolved
    note = payload.get("note", "Resolved by finance operator")
    actor_id = payload.get("actor_id", "human_operator")

    exp = await db_container.db.exceptions.find_one({"exception_id": exception_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    new_status = "APPROVED" if action == "approve" else ("REJECTED" if action == "reject" else ("RESOLVED" if action == "resolve" else "HUMAN_REVIEW"))

    terminal_states = {"APPROVED", "REJECTED", "RESOLVED"}
    current_status = exp.get("status")

    if current_status in terminal_states:
        # User requested 409 on invalid transition
        raise HTTPException(status_code=409, detail="Exception has already reached a terminal state.")

    await db_container.db.exceptions.update_one(
        {"exception_id": exception_id},
        {"$set": {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    import hashlib
    import json
    last_hash = await db_container.db.audit_logs.find_one(sort=[("timestamp", -1)])
    previous_hash = last_hash.get("event_hash") if last_hash else None

    audit_id = f"AUD_{uuid.uuid4().hex[:12]}"
    audit_doc = {
        "audit_id": audit_id,
        "run_id": exp.get("run_id"),
        "transaction_id": exp.get("transaction_id"),
        "actor_type": "HUMAN",
        "actor_id": actor_id,
        "action": f"HUMAN_{action.upper()}",
        "previous_state": exp.get("status"),
        "new_state": new_status,
        "reason": note,
        "evidence": {"note": note, "action": action},
        "confidence": 1.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {"exception_id": exception_id},
        "previous_hash": previous_hash
    }

    canonical_payload = json.dumps(audit_doc, sort_keys=True)
    event_hash = hashlib.sha256((str(previous_hash) + canonical_payload).encode()).hexdigest()
    audit_doc["event_hash"] = event_hash
    audit_doc["timestamp"] = datetime.fromisoformat(audit_doc["timestamp"])

    await db_container.db.audit_logs.insert_one(audit_doc)

    return {
        "status": "success",
        "exception_id": exception_id,
        "action": action,
        "new_status": new_status,
        "note": note
    }
