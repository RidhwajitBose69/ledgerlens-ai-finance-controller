from typing import Dict, Any
from backend.app.core.config import settings

ALLOWED_AUTO_RESOLUTION_REASONS = {"FEE_VARIANCE", "TAX_VARIANCE", "DATE_VARIANCE"}
HIGH_RISK_REASONS = {
    "MULTIPLE_CANDIDATES", "UNKNOWN_TRANSACTION", "LARGE_AMOUNT_MISMATCH",
    "MISSING_LEDGER", "MISSING_SETTLEMENT", "CURRENCY_MISMATCH", "REVERSED_TRANSACTION"
}

def evaluate_safety_policy(investigation: Dict[str, Any], exception: Dict[str, Any]) -> Dict[str, Any]:
    confidence = investigation.get("confidence", 0.0)
    reason_code = exception.get("reason_code", "UNKNOWN")
    financial_impact = exception.get("financial_impact_paise", 0)

    is_threshold_met = confidence >= settings.AUTO_RESOLUTION_THRESHOLD
    is_amount_within_limit = financial_impact <= settings.MAX_AUTO_RESOLUTION_AMOUNT
    is_reason_allowed = reason_code in ALLOWED_AUTO_RESOLUTION_REASONS
    is_not_high_risk = reason_code not in HIGH_RISK_REASONS

    is_auto_resolve_permitted = (
        investigation.get("decision") == "AUTO_RESOLVE" and
        is_threshold_met and
        is_amount_within_limit and
        is_reason_allowed and
        is_not_high_risk
    )

    policy_reason = "Policy criteria satisfied for automated resolution."
    if not is_threshold_met:
        policy_reason = f"Confidence ({confidence:.2f}) below required threshold ({settings.AUTO_RESOLUTION_THRESHOLD})."
    elif not is_amount_within_limit:
        policy_reason = f"Financial impact (INR {financial_impact/100:.2f}) exceeds maximum auto-resolution limit (INR {settings.MAX_AUTO_RESOLUTION_AMOUNT/100:.2f})."
    elif not is_reason_allowed:
        policy_reason = f"Reason code '{reason_code}' is not permitted for automated resolution."
    elif not is_not_high_risk:
        policy_reason = f"Reason code '{reason_code}' is considered high risk."

    final_decision = "AUTO_RESOLVE" if is_auto_resolve_permitted else "HUMAN_REVIEW"

    return {
        "allowed": is_auto_resolve_permitted,
        "is_auto_resolve_permitted": is_auto_resolve_permitted,
        "final_decision": final_decision,
        "policy_reason": policy_reason,
        "reason": policy_reason,
        "confidence": confidence,
        "policy_threshold": settings.AUTO_RESOLUTION_THRESHOLD,
        "amount_limit_paise": settings.MAX_AUTO_RESOLUTION_AMOUNT,
        "checks": [
            {"check": "threshold_met", "passed": is_threshold_met},
            {"check": "amount_within_limit", "passed": is_amount_within_limit},
            {"check": "reason_allowed", "passed": is_reason_allowed},
            {"check": "not_high_risk", "passed": is_not_high_risk}
        ]
    }
