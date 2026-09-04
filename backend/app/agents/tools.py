from typing import Dict, Any, Optional, List
from backend.app.db.mongo import db_container

async def tool_get_transaction(transaction_id: str) -> Optional[Dict[str, Any]]:
    return await db_container.db.transactions.find_one({"transaction_id": transaction_id}, {"_id": 0})

async def tool_get_settlement(settlement_id: str) -> Optional[Dict[str, Any]]:
    return await db_container.db.settlements.find_one({"settlement_id": settlement_id}, {"_id": 0})

async def tool_get_bank_transaction(bank_transaction_id: str) -> Optional[Dict[str, Any]]:
    return await db_container.db.bank_transactions.find_one({"bank_transaction_id": bank_transaction_id}, {"_id": 0})

async def tool_search_ledger(query: str) -> List[Dict[str, Any]]:
    cursor = db_container.db.transactions.find({
        "$or": [
            {"payment_id": {"$regex": query, "$options": "i"}},
            {"reference_id": {"$regex": query, "$options": "i"}},
            {"order_id": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(10)
    return await cursor.to_list(length=10)

async def tool_search_bank_transaction(query: str) -> List[Dict[str, Any]]:
    cursor = db_container.db.bank_transactions.find({
        "$or": [
            {"reference_id": {"$regex": query, "$options": "i"}},
            {"utr": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(10)
    return await cursor.to_list(length=10)

async def tool_compare_amounts(transaction_id: str) -> Dict[str, Any]:
    tx = await tool_get_transaction(transaction_id)
    if not tx:
        return {"error": f"Transaction {transaction_id} not found"}

    settlement = await db_container.db.settlements.find_one({"payment_id": tx.get("payment_id")}, {"_id": 0})
    l_net = tx.get("expected_settlement", tx.get("gross_amount", 0) - tx.get("fee", 0) - tx.get("tax", 0))
    s_net = settlement.get("net_amount", 0) if settlement else 0

    return {
        "transaction_id": transaction_id,
        "ledger_expected_net_paise": l_net,
        "settlement_net_paise": s_net,
        "difference_paise": s_net - l_net,
        "difference_inr": round((s_net - l_net) / 100.0, 2)
    }

async def tool_check_fees(transaction_id: str) -> Dict[str, Any]:
    tx = await tool_get_transaction(transaction_id)
    if not tx:
        return {"error": f"Transaction {transaction_id} not found"}

    settlement = await db_container.db.settlements.find_one({"payment_id": tx.get("payment_id")}, {"_id": 0})
    recorded_fee = tx.get("recorded_fee", 0)
    actual_fee = settlement.get("fee", 0) if settlement else 0

    return {
        "transaction_id": transaction_id,
        "recorded_fee_paise": recorded_fee,
        "actual_fee_paise": actual_fee,
        "fee_variance_paise": actual_fee - recorded_fee,
        "fee_variance_inr": round((actual_fee - recorded_fee) / 100.0, 2)
    }

async def tool_check_tax(transaction_id: str) -> Dict[str, Any]:
    tx = await tool_get_transaction(transaction_id)
    if not tx:
        return {"error": f"Transaction {transaction_id} not found"}

    settlement = await db_container.db.settlements.find_one({"payment_id": tx.get("payment_id")}, {"_id": 0})
    recorded_tax = tx.get("recorded_tax", 0)
    actual_tax = settlement.get("tax", 0) if settlement else 0

    return {
        "transaction_id": transaction_id,
        "recorded_tax_paise": recorded_tax,
        "actual_tax_paise": actual_tax,
        "tax_variance_paise": actual_tax - recorded_tax,
        "tax_variance_inr": round((actual_tax - recorded_tax) / 100.0, 2)
    }

async def tool_check_transaction_history(transaction_id: str) -> List[Dict[str, Any]]:
    cursor = db_container.db.audit_logs.find({"transaction_id": transaction_id}, {"_id": 0}).sort("timestamp", -1)
    return await cursor.to_list(length=20)

async def tool_find_duplicates(transaction_id: str) -> Dict[str, Any]:
    tx = await tool_get_transaction(transaction_id)
    if not tx:
        return {"candidates": []}

    pid = tx.get("payment_id")
    ref = tx.get("reference_id")

    cursor = db_container.db.settlements.find({
        "$or": [
            {"payment_id": pid},
            {"reference_id": ref}
        ]
    }, {"_id": 0})
    settlements = await cursor.to_list(length=10)

    return {
        "transaction_id": transaction_id,
        "candidate_count": len(settlements),
        "candidates": settlements
    }

async def tool_create_review_case(transaction_id: str, note: str = "") -> Dict[str, Any]:
    await db_container.db.exceptions.update_one(
        {"transaction_id": transaction_id},
        {"$set": {"status": "HUMAN_REVIEW", "recommended_action": f"HUMAN_REVIEW: {note}"}}
    )
    return {"status": "success", "transaction_id": transaction_id, "case_status": "HUMAN_REVIEW"}

async def tool_resolve_exception(transaction_id: str, resolution_type: str = "AUTO_RESOLVED") -> Dict[str, Any]:
    await db_container.db.exceptions.update_one(
        {"transaction_id": transaction_id},
        {"$set": {"status": resolution_type}}
    )
    return {"status": "success", "transaction_id": transaction_id, "resolution_type": resolution_type}
