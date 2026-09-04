from typing import List, Dict, Any
from datetime import datetime


def _parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _deduplicate_candidates(
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Remove duplicate settlement IDs while preserving distinct
    settlement records.
    """

    result = []
    seen_ids = set()

    for candidate in candidates:
        settlement_id = candidate.get("settlement_id")

        if settlement_id in seen_ids:
            continue

        seen_ids.add(settlement_id)
        result.append(candidate)

    return result


def find_settlement_candidates(
    ledger_record: Dict[str, Any],
    settlements: List[Dict[str, Any]],
    date_tolerance_days: int = 3
) -> List[Dict[str, Any]]:
    """
    Generate settlement candidates using a strict hierarchical strategy.

    Priority:
    1. Exact payment_id
    2. Exact reference_id
    3. Exact order_id
    4. Exact UTR

    If strong identifiers are present but do not match any settlement,
    do NOT guess using amount/date alone. This avoids false matches.

    Amount/date fallback is only used when the ledger record does not
    contain any strong identifier.
    """

    def collect_matches(field: str, value: Any) -> List[Dict[str, Any]]:
        if not value:
            return []

        return [
            settlement
            for settlement in settlements
            if settlement.get(field) == value
        ]

    payment_id = ledger_record.get("payment_id")
    reference_id = ledger_record.get("reference_id")
    order_id = ledger_record.get("order_id")
    utr = ledger_record.get("utr")

    # ---------------------------------------------------------
    # 1. Exact payment ID
    # ---------------------------------------------------------

    candidates = collect_matches("payment_id", payment_id)

    if candidates:
        return _deduplicate_candidates(candidates)

    # ---------------------------------------------------------
    # 2. Exact reference ID
    # ---------------------------------------------------------

    candidates = collect_matches("reference_id", reference_id)

    if candidates:
        return _deduplicate_candidates(candidates)

    # ---------------------------------------------------------
    # 3. Exact order ID
    # ---------------------------------------------------------

    candidates = collect_matches("order_id", order_id)

    if candidates:
        return _deduplicate_candidates(candidates)

    # ---------------------------------------------------------
    # 4. Exact UTR
    # ---------------------------------------------------------

    candidates = collect_matches("utr", utr)

    if candidates:
        return _deduplicate_candidates(candidates)

    # ---------------------------------------------------------
    # 5. If strong identifiers exist but none matched,
    #    do NOT perform speculative matching.
    # ---------------------------------------------------------

    has_strong_identifier = any(
        [
            bool(payment_id),
            bool(reference_id),
            bool(order_id),
            bool(utr),
        ]
    )

    if has_strong_identifier:
        return []

    # ---------------------------------------------------------
    # 6. Conservative fallback for records without identifiers
    # ---------------------------------------------------------

    tx_date = _parse_date(
        ledger_record.get("transaction_date")
    )

    if not tx_date:
        return []

    expected_net = ledger_record.get(
        "expected_settlement",
        ledger_record.get("amount", 0)
    )

    if expected_net <= 0:
        return []

    fallback_candidates = []

    for settlement in settlements:

        settlement_date = _parse_date(
            settlement.get("settlement_date")
        )

        if not settlement_date:
            continue

        diff_seconds = abs(
            (settlement_date - tx_date).total_seconds()
        )

        diff_days = diff_seconds / 86400.0

        if diff_days > date_tolerance_days:
            continue

        settlement_net = settlement.get(
            "net_amount",
            settlement.get("settlement_amount", 0)
        )

        if settlement_net <= 0:
            continue

        amount_difference = abs(
            settlement_net - expected_net
        )

        # Maximum fallback tolerance:
        # ₹10 OR 0.25%, whichever is larger.
        amount_tolerance = max(
            1000,
            int(expected_net * 0.0025)
        )

        if amount_difference <= amount_tolerance:
            fallback_candidates.append(settlement)

    return _deduplicate_candidates(fallback_candidates)


def find_bank_candidates(
    settlement_or_ledger: Dict[str, Any],
    bank_records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Find bank transaction candidates using strong identifiers.
    """

    candidates = []
    seen_ids = set()

    reference_id = settlement_or_ledger.get("reference_id")
    utr = settlement_or_ledger.get("utr")

    for bank in bank_records:

        bank_id = bank.get("bank_transaction_id")

        if bank_id in seen_ids:
            continue

        bank_reference = bank.get("reference_id")
        bank_utr = bank.get("utr")

        if (
            reference_id
            and bank_reference
            and reference_id == bank_reference
        ):
            seen_ids.add(bank_id)
            candidates.append(bank)

        elif (
            utr
            and bank_utr
            and utr == bank_utr
        ):
            seen_ids.add(bank_id)
            candidates.append(bank)

    return candidates
