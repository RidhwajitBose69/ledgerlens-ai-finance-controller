import pytest
from datetime import datetime, timedelta
from backend.app.reconciliation.engine import ReconciliationEngine
from backend.app.reconciliation.exact_matching import match_exact_identifiers
from backend.app.reconciliation.fuzzy_matching import calculate_string_similarity
from backend.app.reconciliation.amount_matching import reconcile_amounts

def test_exact_identifier_matching():
    l_rec = {"payment_id": "pay_123", "reference_id": "REF_ABC", "order_id": "ORD_1", "customer_id": "C_1"}
    s_rec = {"payment_id": "pay_123", "reference_id": "REF_ABC", "order_id": "ORD_1", "customer_id": "C_1"}
    res = match_exact_identifiers(l_rec, s_rec)
    assert res["payment_id_match"] is True
    assert res["reference_match"] is True

def test_fuzzy_matching():
    sim = calculate_string_similarity("REF_991001", "REF_991001")
    assert sim == 1.0

    sim_typo = calculate_string_similarity("REF_991001", "REF_991001_ERR")
    assert sim_typo > 0.7

def test_amount_reconciliation():
    l_rec = {"amount": 10000, "recorded_fee": 180, "recorded_tax": 32, "expected_settlement": 9788}
    s_rec = {"settlement_amount": 10000, "fee": 180, "tax": 32, "net_amount": 9788}
    res = reconcile_amounts(l_rec, s_rec)
    assert res["status"] == "EXACT"
    assert res["net_difference"] == 0

    s_fee_var = {"settlement_amount": 10000, "fee": 300, "tax": 32, "net_amount": 9668}
    res_fee = reconcile_amounts(l_rec, s_fee_var)
    assert res_fee["status"] == "FEE_VARIANCE"
    assert res_fee["fee_difference"] == 120

def test_full_reconciliation_exact_match():
    engine = ReconciliationEngine(date_tolerance_days=3)
    tx_date = datetime.utcnow().isoformat()
    l_rec = {
        "transaction_id": "TXN_1",
        "payment_id": "pay_100",
        "reference_id": "REF_100",
        "order_id": "ORD_100",
        "customer_id": "CUST_100",
        "transaction_date": tx_date,
        "amount": 10000,
        "recorded_fee": 180,
        "recorded_tax": 32,
        "expected_settlement": 9788,
        "currency": "INR",
        "status": "captured"
    }
    s_rec = {
        "settlement_id": "set_100",
        "payment_id": "pay_100",
        "reference_id": "REF_100",
        "settlement_date": tx_date,
        "settlement_amount": 10000,
        "fee": 180,
        "tax": 32,
        "net_amount": 9788,
        "settlement_status": "processed",
        "utr": "UTR123"
    }
    b_rec = {
        "bank_transaction_id": "BANK_100",
        "reference_id": "REF_100",
        "amount": 9788,
        "utr": "UTR123"
    }

    matched_ids = set()
    result = engine.reconcile_transaction(
        ledger_record=l_rec,
        settlements=[s_rec],
        bank_records=[b_rec],
        matched_settlement_ids=matched_ids,
        run_id="run_test_1"
    )

    assert result.matched is True
    assert result.match_status == "MATCHED"
    assert result.confidence >= 0.95
    assert result.matched_settlement_id == "set_100"
    assert result.matched_bank_transaction_id == "BANK_100"
