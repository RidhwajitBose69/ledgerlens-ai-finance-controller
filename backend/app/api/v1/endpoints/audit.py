from typing import Optional, Dict, Any
from datetime import datetime
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Query
from backend.app.db.mongo import db_container

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("", response_model=Dict[str, Any])
async def list_audit_logs(
    run_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    query: Dict[str, Any] = {}
    if run_id:
        query["run_id"] = run_id
    if transaction_id:
        query["transaction_id"] = transaction_id
    if actor_type:
        query["actor_type"] = actor_type
    if action:
        query["action"] = action

    skip = (page - 1) * limit
    total = await db_container.db.audit_logs.count_documents(query)
    cursor = db_container.db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "audit_logs": logs
    }

@router.get("/verify", response_model=Dict[str, Any])
async def verify_audit_chain():
    import hashlib
    import json

    cursor = db_container.db.audit_logs.find().sort("timestamp", 1)
    logs = await cursor.to_list(length=None)

    events_checked = 0
    valid = True
    first_invalid = None

    previous_hash = None
    for log in logs:
        expected_hash = log.get("event_hash")
        if expected_hash is None:
            # Legacy or unhashed event
            continue

        payload = {k: v for k, v in log.items() if k not in ["_id", "event_hash"]}
        # pyrefly: ignore [unknown-name]
        if isinstance(payload.get("timestamp"), datetime):
            payload["timestamp"] = payload["timestamp"].isoformat()

        canonical = json.dumps(payload, sort_keys=True)
        computed = hashlib.sha256((str(log.get("previous_hash")) + canonical).encode()).hexdigest()

        if computed != expected_hash or str(previous_hash) != str(log.get("previous_hash")):
            valid = False
            first_invalid = log.get("audit_id")
            break

        events_checked += 1
        previous_hash = expected_hash

    return {
        "valid": valid,
        "events_checked": events_checked,
        "first_invalid_event": first_invalid
    }
