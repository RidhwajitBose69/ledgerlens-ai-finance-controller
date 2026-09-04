import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
# pyrefly: ignore [missing-import]
from pymongo import MongoClient

from backend.app.core.config import settings
from backend.app.db.mongo import get_sync_db
from backend.app.schemas.domain import (
    ReconciliationRun, ReconciliationRunOptions, ReconciliationResult, ExceptionItem, AuditLog
)
from backend.app.reconciliation.engine import ReconciliationEngine
from backend.app.core.risk_engine import calculate_risk
import hashlib
import json

def normalize_ledger_record(tx: dict) -> dict:
    """
    Normalize a DB transaction document to the ledger schema expected by the engine.
    Handles both:
      - ledger.json schema: amount, recorded_fee, recorded_tax, expected_settlement
      - transactions.json schema: gross_amount, fee, tax, net_amount  (legacy, defensive)
    Returns a copy with canonical ledger fields populated.
    """
    # If already has ledger schema, return as-is (fast path)
    if "amount" in tx and "expected_settlement" in tx:
        return tx

    # Defensive: map canonical schema -> ledger schema
    result = dict(tx)
    if "gross_amount" in tx and "amount" not in tx:
        result["amount"] = tx["gross_amount"]
    if "fee" in tx and "recorded_fee" not in tx:
        result["recorded_fee"] = tx["fee"]
    if "tax" in tx and "recorded_tax" not in tx:
        result["recorded_tax"] = tx["tax"]
    if "net_amount" in tx and "expected_settlement" not in tx:
        result["expected_settlement"] = tx["net_amount"]
    return result


def _auto_seed_from_files(db, dataset_id: str = "demo-500"):
    """
    If the transactions collection is empty, auto-seed from data/generated/ledger.json.
    This ensures the API trigger ('Run Reconciliation' button) works even if seed_database.py
    was not run manually.
    """
    import json, os
    dataset_dir = "data/generated"
    ledger_path = os.path.join(dataset_dir, "ledger.json")
    tx_path = os.path.join(dataset_dir, "transactions.json")
    set_path = os.path.join(dataset_dir, "settlements.json")
    bank_path = os.path.join(dataset_dir, "bank_transactions.json")

    # Prefer ledger.json; fall back to transactions.json
    actual_tx_path = ledger_path if os.path.exists(ledger_path) else tx_path

    if not os.path.exists(actual_tx_path):
        return  # No data files available; engine will run with empty collections

    with open(actual_tx_path) as f:
        transactions = json.load(f)
    with open(set_path) as f:
        settlements = json.load(f)
    with open(bank_path) as f:
        bank_records = json.load(f)

    if transactions:
        db.transactions.insert_many(transactions)
    if settlements:
        db.settlements.insert_many(settlements)
    if bank_records:
        db.bank_transactions.insert_many(bank_records)


def execute_reconciliation_run(run_id: str, dataset_id: str = "demo-500", options: Optional[Dict[str, Any]] = None):
    """
    Synchronous / Background execution worker for reconciliation runs.
    Reads transactions, settlements, bank records from DB, executes engine,
    and writes results, exceptions, and audit logs to MongoDB.
    """
    db = get_sync_db()
    opts = options or {}
    date_tol = opts.get("date_tolerance_days", settings.SETTLEMENT_DATE_TOLERANCE_DAYS)

    start_time = time.time()

    db.reconciliation_runs.update_one(
        {"run_id": run_id},
        {"$set": {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": "processing",
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    transactions = list(db.transactions.find())
    settlements = list(db.settlements.find())
    bank_records = list(db.bank_transactions.find())

    # Auto-seed from data files if DB is empty (e.g. fresh container or first run)
    if not transactions:
        _auto_seed_from_files(db, dataset_id)
        transactions = list(db.transactions.find())
        settlements = list(db.settlements.find())
        bank_records = list(db.bank_transactions.find())

    # Normalize ledger records: ensure engine always sees the correct field names
    # (amount, recorded_fee, recorded_tax, expected_settlement) even if the seeded
    # collection uses the canonical schema (gross_amount, fee, tax, net_amount).
    transactions = [normalize_ledger_record(tx) for tx in transactions]

    engine = ReconciliationEngine(date_tolerance_days=date_tol)

    total_records = len(transactions)
    processed_count = 0
    matched_count = 0
    exception_count = 0
    reconciled_amount = 0
    unreconciled_amount = 0

    matched_settlement_ids = set()
    results = []
    exceptions = []
    audit_logs = []
    seen_exceptions = set()

    for tx in transactions:
        result: ReconciliationResult = engine.reconcile_transaction(
            ledger_record=normalize_ledger_record(tx),
            settlements=settlements,
            bank_records=bank_records,
            matched_settlement_ids=matched_settlement_ids,
            run_id=run_id
        )

        processed_count += 1
        res_dict = result.model_dump()
        res_dict["created_at"] = datetime.now(timezone.utc)
        results.append(res_dict)

        last_hash = db.audit_logs.find_one(sort=[("timestamp", -1)])
        previous_hash = last_hash.get("event_hash") if last_hash else None

        if result.matched:
            matched_count += 1
            reconciled_amount += result.evidence.ledger_amount_paise
            # System audit log for exact match
            audit_id = f"AUD_{uuid.uuid4().hex[:12]}"
            payload = {
                "audit_id": audit_id,
                "run_id": run_id,
                "transaction_id": result.transaction_id,
                "actor_type": "SYSTEM",
                "actor_id": "reconciliation-engine",
                "action": "MATCH_DETECTED",
                "previous_state": "UNPROCESSED",
                "new_state": "MATCHED",
                "reason": "Exact deterministic match identified",
                "evidence": result.evidence.model_dump(),
                "confidence": result.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"matched_settlement_id": result.matched_settlement_id},
                "previous_hash": previous_hash
            }
            canonical_payload = json.dumps(payload, sort_keys=True)
            event_hash = hashlib.sha256((str(previous_hash) + canonical_payload).encode()).hexdigest()
            payload["event_hash"] = event_hash
            payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
            audit_logs.append(payload)
            previous_hash = event_hash
        else:
            exception_count += 1
            unreconciled_amount += result.evidence.ledger_amount_paise

            exp_key = (result.transaction_id, result.reason_code)
            if exp_key in seen_exceptions:
                continue
            seen_exceptions.add(exp_key)

            financial_impact = abs(result.financial_difference_paise)
            risk_result = calculate_risk({
                "financial_impact_paise": financial_impact,
                "reason_code": result.reason_code,
                "confidence": result.confidence
            })

            priority = risk_result["priority"]
            priority_score = risk_result["priority_score"]
            risk_level = risk_result["priority"]

            rec_action = "AI_INVESTIGATION" if result.reason_code in ["FEE_VARIANCE", "TAX_VARIANCE", "DATE_VARIANCE"] else "HUMAN_REVIEW"

            exp_item = {
                "exception_id": f"EXP_{uuid.uuid4().hex[:12]}",
                "run_id": run_id,
                "transaction_id": result.transaction_id,
                "reason_code": result.reason_code,
                "priority": priority,
                "priority_score": round(priority_score, 2),
                "status": "DETECTED",
                "financial_impact_paise": financial_impact,
                "confidence": result.confidence,
                "age_days": 0.0,
                "sla_status": "WITHIN_SLA",
                "recommended_action": rec_action,
                "risk_level": risk_level,
                "matched_settlement_id": result.matched_settlement_id,
                "matched_bank_transaction_id": result.matched_bank_transaction_id,
                "evidence": result.evidence.model_dump(),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            exceptions.append(exp_item)

            audit_id = f"AUD_{uuid.uuid4().hex[:12]}"
            payload = {
                "audit_id": audit_id,
                "run_id": run_id,
                "transaction_id": result.transaction_id,
                "actor_type": "SYSTEM",
                "actor_id": "reconciliation-engine",
                "action": "EXCEPTION_DETECTED",
                "previous_state": "UNPROCESSED",
                "new_state": "DETECTED",
                "reason": f"Discrepancy detected: {result.reason_code}",
                "evidence": result.evidence.model_dump(),
                "confidence": result.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"exception_id": exp_item["exception_id"], "priority": priority},
                "previous_hash": previous_hash
            }
            canonical_payload = json.dumps(payload, sort_keys=True)
            event_hash = hashlib.sha256((str(previous_hash) + canonical_payload).encode()).hexdigest()
            payload["event_hash"] = event_hash
            payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
            audit_logs.append(payload)
            previous_hash = event_hash

        # Periodic status update in Mongo
        if processed_count % 100 == 0 or processed_count == total_records:
            db.reconciliation_runs.update_one(
                {"run_id": run_id},
                {"$set": {
                    "processed_records": processed_count,
                    "matched_count": matched_count,
                    "exception_count": exception_count,
                    "reconciled_amount_paise": reconciled_amount,
                    "unreconciled_amount_paise": unreconciled_amount
                }}
            )

    # Bulk insert results, exceptions, audit logs
    if results:
        db.reconciliation_results.insert_many(results)
    if exceptions:
        db.exceptions.insert_many(exceptions)
    if audit_logs:
        db.audit_logs.insert_many(audit_logs)

    total_time_ms = (time.time() - start_time) * 1000.0

    db.reconciliation_runs.update_one(
        {"run_id": run_id},
        {"$set": {
            "status": "completed",
            "total_records": total_records,
            "processed_records": processed_count,
            "matched_count": matched_count,
            "exception_count": exception_count,
            "reconciled_amount_paise": reconciled_amount,
            "unreconciled_amount_paise": unreconciled_amount,
            "total_processing_time_ms": round(total_time_ms, 2),
            "completed_at": datetime.now(timezone.utc)
        }}
    )
