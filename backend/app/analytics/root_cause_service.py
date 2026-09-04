from typing import List, Dict, Any

def analyze_root_causes(exceptions: List[Dict[str, Any]], transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tx_map = {t["transaction_id"]: t for t in transactions}

    # Group exceptions by (reason_code, payment_method)
    groups: Dict[tuple, List[Dict[str, Any]]] = {}

    for exp in exceptions:
        tx_id = exp.get("transaction_id")
        tx = tx_map.get(tx_id, {})
        method = tx.get("payment_method", "unknown")
        reason = exp.get("reason_code", "UNKNOWN")

        key = (reason, method)
        groups.setdefault(key, []).append(exp)

    root_causes = []
    for (reason, method), exp_list in groups.items():
        count = len(exp_list)
        total_impact = sum(e.get("financial_impact_paise", 0) for e in exp_list)
        sample_ids = [e.get("transaction_id") for e in exp_list[:5]]

        # Title and systemic pattern detection
        title = f"Systemic {reason.replace('_', ' ').title()} Anomaly"
        description = f"Detected {count} instances of {reason} on {method.upper()} payment transactions."

        if reason == "FEE_VARIANCE" and count >= 5:
            title = f"Systemic Fee Configuration Discrepancy on {method.upper()}"
            description = f"Gateway applied non-standard fee structure across {count} {method.upper()} transactions."
        elif reason == "TAX_VARIANCE" and count >= 5:
            title = f"GST Tax Calculation Variance on {method.upper()}"
            description = f"Tax calculation mismatch identified across {count} settled transactions."
        elif reason == "DATE_VARIANCE" and count >= 5:
            title = f"Delayed Gateway Settlement Batch on {method.upper()}"
            description = f"Settlement timing exceeded 3-day SLA for {count} transactions."
        elif reason == "MISSING_SETTLEMENT" and count >= 3:
            title = f"Unsettled Payment Ledger Entries on {method.upper()}"
            description = f"{count} captured payments have no matching settlement record from gateway."

        root_causes.append({
            "root_cause_id": f"RC_{reason}_{method}",
            "title": title,
            "description": description,
            "reason_code": reason,
            "payment_method": method,
            "affected_count": count,
            "total_financial_impact_paise": total_impact,
            "total_financial_impact_inr": round(total_impact / 100.0, 2),
            "sample_transaction_ids": sample_ids,
            "severity": "HIGH" if count >= 10 or total_impact >= 500000 else "MEDIUM"
        })

    root_causes.sort(key=lambda x: (x["affected_count"], x["total_financial_impact_paise"]), reverse=True)
    return root_causes
