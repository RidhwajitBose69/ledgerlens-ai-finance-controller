from datetime import datetime
from typing import Dict, Any

def reconcile_dates(
    ledger_record: Dict[str, Any],
    settlement_record: Dict[str, Any],
    tolerance_days: int = 3
) -> Dict[str, Any]:
    l_date_str = ledger_record.get("transaction_date")
    s_date_str = settlement_record.get("settlement_date")

    if not l_date_str or not s_date_str:
        return {
            "difference_days": 0,
            "compatible": True,
            "exceeds_tolerance": False
        }

    try:
        l_date = datetime.fromisoformat(str(l_date_str).replace("Z", "+00:00"))
        s_date = datetime.fromisoformat(str(s_date_str).replace("Z", "+00:00"))

        diff_days = (s_date - l_date).days
        abs_diff_days = abs(diff_days)

        exceeds_tolerance = abs_diff_days > tolerance_days
        compatible = not exceeds_tolerance

        return {
            "ledger_date": l_date.isoformat(),
            "settlement_date": s_date.isoformat(),
            "difference_days": diff_days,
            "abs_difference_days": abs_diff_days,
            "compatible": compatible,
            "exceeds_tolerance": exceeds_tolerance
        }
    except Exception:
        return {
            "difference_days": 0,
            "compatible": True,
            "exceeds_tolerance": False
        }
