from typing import Dict, Any

def match_exact_identifiers(ledger_record: Dict[str, Any], settlement_record: Dict[str, Any]) -> Dict[str, Any]:
    payment_id_match = (
        ledger_record.get("payment_id") is not None and
        ledger_record.get("payment_id") == settlement_record.get("payment_id")
    )
    reference_match = (
        ledger_record.get("reference_id") is not None and
        ledger_record.get("reference_id") == settlement_record.get("reference_id")
    )
    order_id_match = (
        ledger_record.get("order_id") is not None and
        ledger_record.get("order_id") == settlement_record.get("order_id")
    )
    customer_match = (
        ledger_record.get("customer_id") is not None and
        ledger_record.get("customer_id") == settlement_record.get("customer_id")
    )

    return {
        "payment_id_match": payment_id_match,
        "reference_match": reference_match,
        "order_id_match": order_id_match,
        "customer_match": customer_match
    }
