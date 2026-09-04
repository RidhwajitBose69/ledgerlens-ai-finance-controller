import pytest
from backend.app.agents.policies import evaluate_safety_policy
from backend.app.agents.providers.mock import MockAIProvider

@pytest.mark.asyncio
async def test_mock_agent_provider():
    provider = MockAIProvider()
    exp = {"reason_code": "FEE_VARIANCE", "financial_impact_paise": 1500, "confidence": 0.92}
    ctx = {"transaction": {"transaction_id": "TXN_1"}, "settlement": {"settlement_id": "set_1"}}

    res = await provider.investigate_exception(exp, ctx)
    assert res["decision"] == "AUTO_RESOLVE"
    assert res["confidence"] >= 0.95
    assert len(res["evidence_items"]) > 0

def test_safety_policy_enforcement():
    investigation = {"decision": "AUTO_RESOLVE", "confidence": 0.96}
    fee_exp = {"reason_code": "FEE_VARIANCE", "financial_impact_paise": 1500}

    policy_fee = evaluate_safety_policy(investigation, fee_exp)
    assert policy_fee["is_auto_resolve_permitted"] is True
    assert policy_fee["final_decision"] == "AUTO_RESOLVE"

    dup_exp = {"reason_code": "DUPLICATE", "financial_impact_paise": 1500}
    policy_dup = evaluate_safety_policy(investigation, dup_exp)
    assert policy_dup["is_auto_resolve_permitted"] is False
    assert policy_dup["final_decision"] == "HUMAN_REVIEW"
