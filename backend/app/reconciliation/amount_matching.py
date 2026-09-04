from typing import Dict, Any

def reconcile_amounts(ledger_record: Dict[str, Any], settlement_record: Dict[str, Any]) -> Dict[str, Any]:
    l_gross = ledger_record.get("amount", ledger_record.get("gross_amount", 0))
    l_fee = ledger_record.get("recorded_fee", ledger_record.get("fee", 0))
    l_tax = ledger_record.get("recorded_tax", ledger_record.get("tax", 0))
    l_expected_net = ledger_record.get("expected_settlement", l_gross - l_fee - l_tax)

    s_gross = settlement_record.get("settlement_amount", settlement_record.get("gross_amount", 0))
    s_fee = settlement_record.get("fee", 0)
    s_tax = settlement_record.get("tax", 0)
    s_net = settlement_record.get("net_amount", s_gross - s_fee - s_tax)

    gross_diff = s_gross - l_gross
    fee_diff = s_fee - l_fee
    tax_diff = s_tax - l_tax
    net_diff = s_net - l_expected_net

    status = "EXACT"

    if net_diff == 0 and fee_diff == 0 and tax_diff == 0:
        status = "EXACT"
    elif gross_diff == 0 and tax_diff == 0 and fee_diff != 0:
        status = "FEE_VARIANCE"
    elif gross_diff == 0 and fee_diff == 0 and tax_diff != 0:
        status = "TAX_VARIANCE"
    elif gross_diff == 0 and (fee_diff != 0 or tax_diff != 0):
        status = "COMBINED_FEE_TAX"
    elif s_net < l_expected_net and s_net > 0:
        status = "PARTIAL_SETTLEMENT"
    else:
        status = "AMOUNT_MISMATCH"

    return {
        "status": status,
        "ledger_gross": l_gross,
        "ledger_fee": l_fee,
        "ledger_tax": l_tax,
        "ledger_expected_net": l_expected_net,
        "settlement_gross": s_gross,
        "settlement_fee": s_fee,
        "settlement_tax": s_tax,
        "settlement_net": s_net,
        "gross_difference": gross_diff,
        "fee_difference": fee_diff,
        "tax_difference": tax_diff,
        "net_difference": net_diff,
        "compatible": status in ["EXACT", "FEE_VARIANCE", "TAX_VARIANCE", "COMBINED_FEE_TAX"]
    }
