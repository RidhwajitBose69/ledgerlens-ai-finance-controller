from typing import Dict, Any, Optional

def classify_reconciliation_result(
    ledger_record: Optional[Dict[str, Any]],
    best_candidate: Optional[Dict[str, Any]],
    score_details: Optional[Dict[str, Any]],
    candidate_count: int,
    bank_candidate: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    if not ledger_record and best_candidate:
        return {
            "match_status": "MISSING_LEDGER",
            "reason_code": "MISSING_LEDGER",
            "confidence": 0.50,
            "matched": False,
            "financial_difference_paise": best_candidate.get("net_amount", 0)
        }

    if ledger_record and not best_candidate:
        return {
            "match_status": "MISSING_SETTLEMENT",
            "reason_code": "MISSING_SETTLEMENT",
            "confidence": 0.40,
            "matched": False,
            "financial_difference_paise": ledger_record.get("expected_settlement", 0)
        }

    if ledger_record.get("status") in ["reversed", "failed"]:
        return {
            "match_status": "REVERSED_TRANSACTION" if ledger_record.get("status") == "reversed" else "FAILED_PAYMENT",
            "reason_code": "REVERSED_TRANSACTION" if ledger_record.get("status") == "reversed" else "FAILED_PAYMENT",
            "confidence": 0.70,
            "matched": False,
            "financial_difference_paise": ledger_record.get("expected_settlement", 0)
        }

    if ledger_record.get("currency") != "INR":
        return {
            "match_status": "CURRENCY_MISMATCH",
            "reason_code": "CURRENCY_MISMATCH",
            "confidence": 0.60,
            "matched": False,
            "financial_difference_paise": ledger_record.get("expected_settlement", 0)
        }
    # A settlement match is not sufficient for full reconciliation.
    # The settlement must also be traceable to a bank transaction.
    # Without a bank-side confirmation, the transaction remains unknown.
    if best_candidate and bank_candidate is None:
        return {
            "match_status": "UNKNOWN_TRANSACTION",
            "reason_code": "UNKNOWN_TRANSACTION",
            "confidence": 0.60,
            "matched": False,
            "financial_difference_paise": 0
        }

    if candidate_count > 1:
        return {
            "match_status": "DUPLICATE",
            "reason_code": "MULTIPLE_CANDIDATES" if candidate_count > 1 else "DUPLICATE",
            "confidence": 0.75,
            "matched": False,
            "financial_difference_paise": abs(score_details["amount_res"]["net_difference"]) if score_details else 0
        }

    total_score = score_details["total_score"]
    amount_res = score_details["amount_res"]
    date_res = score_details["date_res"]
    ref_sim = score_details["ref_similarity"]

    confidence = round(total_score / 100.0, 2)
    amount_status = amount_res["status"]

    if amount_status == "EXACT" and date_res["compatible"] and ref_sim >= 0.9:
        return {
            "match_status": "MATCHED",
            "reason_code": "EXACT_MATCH",
            "confidence": max(0.95, confidence),
            "matched": True,
            "financial_difference_paise": 0
        }
    elif amount_status == "FEE_VARIANCE":
        return {
            "match_status": "FEE_VARIANCE",
            "reason_code": "FEE_VARIANCE",
            "confidence": 0.92,
            "matched": False,
            "financial_difference_paise": abs(amount_res["fee_difference"])
        }
    elif amount_status == "TAX_VARIANCE":
        return {
            "match_status": "TAX_VARIANCE",
            "reason_code": "TAX_VARIANCE",
            "confidence": 0.90,
            "matched": False,
            "financial_difference_paise": abs(amount_res["tax_difference"])
        }
    elif date_res["exceeds_tolerance"]:
        return {
            "match_status": "DATE_VARIANCE",
            "reason_code": "DATE_VARIANCE",
            "confidence": 0.85,
            "matched": False,
            "financial_difference_paise": abs(amount_res["net_difference"])
        }
    elif amount_status == "PARTIAL_SETTLEMENT":
        return {
            "match_status": "PARTIAL_SETTLEMENT",
            "reason_code": "PARTIAL_SETTLEMENT",
            "confidence": 0.80,
            "matched": False,
            "financial_difference_paise": abs(amount_res["net_difference"])
        }
    elif ref_sim < 0.8:
        return {
            "match_status": "REFERENCE_MISMATCH",
            "reason_code": "REFERENCE_MISMATCH",
            "confidence": 0.70,
            "matched": False,
            "financial_difference_paise": abs(amount_res["net_difference"])
        }
    else:
        return {
            "match_status": "AMOUNT_MISMATCH",
            "reason_code": "AMOUNT_MISMATCH",
            "confidence": confidence,
            "matched": False,
            "financial_difference_paise": abs(amount_res["net_difference"])
        }
