import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.core.config import settings
from backend.app.db.mongo import db_container
from backend.app.agents.providers.mock import MockAIProvider
from backend.app.agents.providers.openai import OpenAIProvider
from backend.app.agents.providers.gemini import GeminiProvider
from backend.app.agents.policies import evaluate_safety_policy

class FinanceControllerAgent:
    def __init__(self):
        self.providers = {
            "mock": MockAIProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider()
        }

    def get_provider(self, provider_name: str = None):
        name = (provider_name or settings.LLM_PROVIDER).lower()
        return self.providers.get(name, self.providers["mock"])

    async def investigate_exception(
        self,
        exception_id: str,
        provider_name: str = None,
        force: bool = False
    ) -> Dict[str, Any]:

        if not force:
            existing = await db_container.db.agent_investigations.find_one({"exception_id": exception_id}, {"_id": 0})
            if existing:
                return existing

        exp = await db_container.db.exceptions.find_one({"exception_id": exception_id}, {"_id": 0})
        if not exp:
            raise ValueError(f"Exception {exception_id} not found")

        tx_id = exp.get("transaction_id")
        transaction = await db_container.db.transactions.find_one({"transaction_id": tx_id}, {"_id": 0})

        settlement = None
        if exp.get("matched_settlement_id"):
            settlement = await db_container.db.settlements.find_one({"settlement_id": exp.get("matched_settlement_id")}, {"_id": 0})
        elif transaction:
            settlement = await db_container.db.settlements.find_one({"payment_id": transaction.get("payment_id")}, {"_id": 0})

        context_data = {
            "transaction": transaction,
            "settlement": settlement
        }

        provider = self.get_provider(provider_name)
        investigation_result = await provider.investigate_exception(exp, context_data)

        # Apply Safety Policy Engine
        policy_res = evaluate_safety_policy(investigation_result, exp)

        final_status = "AI_RECOMMENDED"
        if policy_res["is_auto_resolve_permitted"]:
            final_status = "AUTO_RESOLVED"

        # Determine next version
        existing_investigations = await db_container.db.agent_investigations.count_documents({"exception_id": exception_id})
        version = existing_investigations + 1

        inv_id = f"INV_{uuid.uuid4().hex[:12]}"
        investigation_doc = {
            "investigation_id": inv_id,
            "exception_id": exception_id,
            "run_id": exp.get("run_id"),
            "transaction_id": tx_id,
            "provider": provider.name(),
            "model_metadata": provider.name(),
            "decision": investigation_result["decision"],
            "policy_decision": policy_res["final_decision"],
            "policy_permitted": policy_res["is_auto_resolve_permitted"],
            "policy_reason": policy_res["policy_reason"],
            "confidence": investigation_result["confidence"],
            "reason_code": investigation_result["reason_code"],
            "summary": investigation_result["summary"],
            "evidence": investigation_result["evidence_items"],
            "evidence_items": investigation_result["evidence_items"],
            "tool_calls": investigation_result["tool_calls"],
            "recommendation": investigation_result["recommended_action"],
            "recommended_action": investigation_result["recommended_action"],
            "risk_level": investigation_result["risk_level"],
            "financial_impact_paise": investigation_result["financial_impact_paise"],
            "version": version,
            "created_at": datetime.now(timezone.utc)
        }

        await db_container.db.agent_investigations.update_one(
            {"exception_id": exception_id},
            {"$set": investigation_doc},
            upsert=True
        )

        # Update Exception document in MongoDB
        await db_container.db.exceptions.update_one(
            {"exception_id": exception_id},
            {"$set": {
                "status": final_status,
                "confidence": investigation_result["confidence"],
                "recommended_action": investigation_result["recommended_action"],
                "risk_level": investigation_result["risk_level"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        import hashlib
        import json
        last_hash = await db_container.db.audit_logs.find_one(sort=[("timestamp", -1)])
        previous_hash = last_hash.get("event_hash") if last_hash else None

        # Record Audit Log
        audit_id = f"AUD_{uuid.uuid4().hex[:12]}"
        payload = {
            "audit_id": audit_id,
            "run_id": exp.get("run_id"),
            "transaction_id": tx_id,
            "actor_type": "AI_AGENT",
            "actor_id": f"agent_{provider.name().lower()}",
            "action": "AI_INVESTIGATION_COMPLETED",
            "previous_state": exp.get("status"),
            "new_state": final_status,
            "reason": investigation_result["summary"],
            "evidence": {"evidence_items": investigation_result["evidence_items"], "policy": policy_res},
            "confidence": investigation_result["confidence"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"investigation_id": inv_id, "provider": provider.name()},
            "previous_hash": previous_hash
        }
        canonical_payload = json.dumps(payload, sort_keys=True)
        event_hash = hashlib.sha256((str(previous_hash) + canonical_payload).encode()).hexdigest()
        payload["event_hash"] = event_hash
        payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])

        await db_container.db.audit_logs.insert_one(payload)

        return investigation_doc
