from typing import Dict, Any
from backend.app.schemas.domain import ScoreBreakdown
from backend.app.reconciliation.exact_matching import match_exact_identifiers
from backend.app.reconciliation.fuzzy_matching import calculate_string_similarity
from backend.app.reconciliation.amount_matching import reconcile_amounts
from backend.app.reconciliation.date_matching import reconcile_dates

def score_candidate(
    ledger_record: Dict[str, Any],
    settlement_record: Dict[str, Any],
    date_tolerance_days: int = 3
) -> Dict[str, Any]:
    exact_res = match_exact_identifiers(ledger_record, settlement_record)
    ref_sim = calculate_string_similarity(
        ledger_record.get("reference_id", ""),
        settlement_record.get("reference_id", "")
    )
    amount_res = reconcile_amounts(ledger_record, settlement_record)
    date_res = reconcile_dates(ledger_record, settlement_record, date_tolerance_days)

    payment_id_score = 40 if exact_res["payment_id_match"] else 0
    ref_score = 20 if exact_res["reference_match"] else int(round(ref_sim * 20))
    order_score = 15 if exact_res["order_id_match"] else 0
    amount_score = 15 if amount_res["compatible"] else 0
    date_score = 5 if date_res["compatible"] else 0
    customer_score = 5 if exact_res["customer_match"] else 0

    total = payment_id_score + ref_score + order_score + amount_score + date_score + customer_score

    score_breakdown = ScoreBreakdown(
        payment_id_exact=payment_id_score,
        reference_exact=20 if exact_res["reference_match"] else 0,
        reference_fuzzy_score=round(ref_sim, 2),
        order_id_exact=order_score,
        amount_compatible=amount_score,
        date_compatible=date_score,
        customer_compatible=customer_score,
        total_score=total
    )

    return {
        "score_breakdown": score_breakdown,
        "total_score": total,
        "exact_res": exact_res,
        "ref_similarity": ref_sim,
        "amount_res": amount_res,
        "date_res": date_res
    }
