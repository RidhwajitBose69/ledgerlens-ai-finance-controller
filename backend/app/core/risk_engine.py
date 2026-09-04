from typing import Dict, Any, List

def calculate_risk(exception: Dict[str, Any]) -> Dict[str, Any]:
    financial_impact = abs(exception.get("financial_impact_paise", 0))
    reason_code = exception.get("reason_code", "UNKNOWN")
    confidence = exception.get("confidence", 0.0)

    priority_score = (1.0 - confidence) * 100.0
    priority = "LOW"
    risk_factors: List[Dict[str, Any]] = []

    if financial_impact >= 500000:
        priority = "CRITICAL"
        priority_score += 40.0
        risk_factors.append({"factor": "High Financial Impact", "weight": 40.0, "reason": "Impact >= 500,000 paise"})
    elif financial_impact >= 100000:
        priority = max(priority, "HIGH", key=lambda x: {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[x])
        priority_score += 25.0
        risk_factors.append({"factor": "Significant Financial Impact", "weight": 25.0, "reason": "Impact >= 100,000 paise"})
    elif financial_impact >= 10000:
        priority = max(priority, "MEDIUM", key=lambda x: {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[x])
        priority_score += 10.0
        risk_factors.append({"factor": "Moderate Financial Impact", "weight": 10.0, "reason": "Impact >= 10,000 paise"})

    if reason_code in ["MULTIPLE_CANDIDATES", "CURRENCY_MISMATCH"]:
        priority = "CRITICAL"
        priority_score += 30.0
        risk_factors.append({"factor": "Critical Reason Code", "weight": 30.0, "reason": f"{reason_code} indicates high operational risk"})
    elif reason_code in ["MISSING_LEDGER", "MISSING_SETTLEMENT", "PARTIAL_SETTLEMENT", "REVERSED_TRANSACTION"]:
        priority = max(priority, "HIGH", key=lambda x: {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[x])
        priority_score += 20.0
        risk_factors.append({"factor": "High Risk Reason Code", "weight": 20.0, "reason": f"{reason_code} indicates missing or reversed data"})

    if priority_score > 100.0:
        priority_score = 100.0

    return {
        "priority": priority,
        "priority_score": round(priority_score, 2),
        "risk_factors": risk_factors
    }
