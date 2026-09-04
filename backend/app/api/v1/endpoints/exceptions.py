from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.app.db.mongo import db_container

router = APIRouter(prefix="/exceptions", tags=["Exceptions"])


def _normalize_tx_for_api(tx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Normalize a transaction document from the DB to always expose the ledger-schema
    fields that the frontend workbench expects:
        .amount, .recorded_fee, .recorded_tax, .expected_settlement

    Handles both:
      - ledger.json schema   → amount / recorded_fee / recorded_tax / expected_settlement
      - transactions.json schema → gross_amount / fee / tax / net_amount  (defensive)
    Returns None if tx is None.
    """
    if tx is None:
        return None
    result = dict(tx)
    # Map canonical schema fields → ledger schema if not already present
    if "amount" not in result and "gross_amount" in result:
        result["amount"] = result["gross_amount"]
    if "recorded_fee" not in result and "fee" in result:
        result["recorded_fee"] = result["fee"]
    if "recorded_tax" not in result and "tax" in result:
        result["recorded_tax"] = result["tax"]
    if "expected_settlement" not in result and "net_amount" in result:
        result["expected_settlement"] = result["net_amount"]
    return result


def _build_transaction_from_evidence(exp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    When no transaction document can be found in the DB, reconstruct a minimal
    display-safe transaction dict from the exception's embedded evidence.
    This guarantees the workbench always shows non-zero financial data.
    """
    evidence = exp.get("evidence") or {}
    if not evidence:
        return None
    ledger_amount = evidence.get("ledger_amount_paise", 0)
    if ledger_amount == 0:
        return None
    return {
        "transaction_id": exp.get("transaction_id"),
        "amount": ledger_amount,
        "recorded_fee": evidence.get("fee_difference_paise", 0),   # best available proxy
        "recorded_tax": evidence.get("tax_difference_paise", 0),
        "expected_settlement": ledger_amount - evidence.get("amount_difference_paise", 0),
        "_source": "evidence_reconstruction"  # flag for diagnostics
    }


@router.get("", response_model=Dict[str, Any])
async def list_exceptions(
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    reason_code: Optional[str] = None,
    priority: Optional[str] = None,
    min_amount: Optional[int] = None,
    max_amount: Optional[int] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    query: Dict[str, Any] = {}
    if run_id:
        query["run_id"] = run_id
    if status:
        query["status"] = status
    if reason_code:
        query["reason_code"] = reason_code
    if priority:
        query["priority"] = priority
    if min_amount is not None:
        query["financial_impact_paise"] = {"$gte": min_amount}
    if max_amount is not None:
        query.setdefault("financial_impact_paise", {})["$lte"] = max_amount
    if min_confidence is not None:
        query["confidence"] = {"$gte": min_confidence}
    if max_confidence is not None:
        query.setdefault("confidence", {})["$lte"] = max_confidence
    if search:
        query["$or"] = [
            {"transaction_id": {"$regex": search, "$options": "i"}},
            {"reason_code": {"$regex": search, "$options": "i"}},
            {"status": {"$regex": search, "$options": "i"}}
        ]

    skip = (page - 1) * limit
    total = await db_container.db.exceptions.count_documents(query)
    cursor = db_container.db.exceptions.find(query, {"_id": 0}).sort("priority_score", -1).skip(skip).limit(limit)
    exceptions = await cursor.to_list(length=limit)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "exceptions": exceptions
    }


@router.get("/{exception_id}", response_model=Dict[str, Any])
async def get_exception_detail(exception_id: str):
    exp = await db_container.db.exceptions.find_one({"exception_id": exception_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    tx_id = exp.get("transaction_id")

    # --- Fetch and normalize the transaction record ---
    raw_tx = await db_container.db.transactions.find_one({"transaction_id": tx_id}, {"_id": 0})
    transaction = _normalize_tx_for_api(raw_tx)

    # If no transaction found in DB, reconstruct from embedded exception evidence
    # This covers MISSING_SETTLEMENT cases where the ledger record might not be seeded.
    if transaction is None:
        transaction = _build_transaction_from_evidence(exp)

    # Also try to supplement from evidence if amounts are still zero
    if transaction and transaction.get("amount", 0) == 0:
        evidence = exp.get("evidence") or {}
        ledger_paise = evidence.get("ledger_amount_paise", 0)
        if ledger_paise > 0:
            transaction["amount"] = ledger_paise
            if "expected_settlement" not in transaction or transaction.get("expected_settlement", 0) == 0:
                transaction["expected_settlement"] = ledger_paise - abs(evidence.get("amount_difference_paise", 0))

    # --- Settlement lookup ---
    settlement = None
    if exp.get("matched_settlement_id"):
        settlement = await db_container.db.settlements.find_one(
            {"settlement_id": exp.get("matched_settlement_id")}, {"_id": 0}
        )
    elif transaction and transaction.get("payment_id"):
        settlement = await db_container.db.settlements.find_one(
            {"payment_id": transaction.get("payment_id")}, {"_id": 0}
        )

    # --- Bank lookup ---
    bank = None
    if exp.get("matched_bank_transaction_id"):
        bank = await db_container.db.bank_transactions.find_one(
            {"bank_transaction_id": exp.get("matched_bank_transaction_id")}, {"_id": 0}
        )
    elif settlement and settlement.get("utr"):
        bank = await db_container.db.bank_transactions.find_one(
            {"utr": settlement.get("utr")}, {"_id": 0}
        )

    investigation = await db_container.db.agent_investigations.find_one(
        {"exception_id": exception_id}, {"_id": 0}
    )
    audit_cursor = db_container.db.audit_logs.find(
        {"transaction_id": tx_id}, {"_id": 0}
    ).sort("timestamp", -1)
    audit_trail = await audit_cursor.to_list(length=50)

    return {
        "exception": exp,
        "transaction": transaction,
        "settlement": settlement,
        "bank": bank,
        "evidence": exp.get("evidence"),
        "investigation": investigation,
        "audit_trail": audit_trail
    }
