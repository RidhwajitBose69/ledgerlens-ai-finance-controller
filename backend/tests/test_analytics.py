import pytest
from backend.app.analytics.root_cause_service import analyze_root_causes

def test_root_cause_analysis():
    exceptions = [
        {
            "exception_id": "EXC_1",
            "transaction_id": "TXN_1",
            "reason_code": "FEE_VARIANCE",
            "priority": "MEDIUM",
            "financial_impact_paise": 1500
        },
        {
            "exception_id": "EXC_2",
            "transaction_id": "TXN_2",
            "reason_code": "FEE_VARIANCE",
            "priority": "MEDIUM",
            "financial_impact_paise": 1500
        }
    ]
    transactions = [
        {"transaction_id": "TXN_1", "payment_method": "card"},
        {"transaction_id": "TXN_2", "payment_method": "card"}
    ]

    root_causes = analyze_root_causes(exceptions, transactions)
    assert isinstance(root_causes, list)
    assert len(root_causes) > 0
    assert root_causes[0]["affected_count"] == 2
    assert root_causes[0]["total_financial_impact_inr"] == 30.0
