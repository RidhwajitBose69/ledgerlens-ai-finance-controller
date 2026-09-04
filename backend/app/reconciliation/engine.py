import time
from typing import List, Dict, Any
from datetime import datetime

from backend.app.schemas.domain import (
    ReconciliationResult, ScoreBreakdown, Evidence
)
from backend.app.reconciliation.candidate_generation import (
    find_settlement_candidates, find_bank_candidates
)
from backend.app.reconciliation.scoring import score_candidate
from backend.app.reconciliation.classifier import classify_reconciliation_result
from backend.app.reconciliation.duplicate_detection import check_duplicates

class ReconciliationEngine:
    def __init__(self, date_tolerance_days: int = 3, engine_version: str = "reconciliation-engine-v1.0"):
        self.date_tolerance_days = date_tolerance_days
        self.engine_version = engine_version

    def reconcile_transaction(
        self,
        ledger_record: Dict[str, Any],
        settlements: List[Dict[str, Any]],
        bank_records: List[Dict[str, Any]],
        matched_settlement_ids: set,
        run_id: str
    ) -> ReconciliationResult:
        start_time = time.time()

        # Step 1-3: Generate settlement candidates
        candidates = find_settlement_candidates(
            ledger_record, settlements, self.date_tolerance_days
        )

        dup_check = check_duplicates(candidates, matched_settlement_ids)

        best_candidate = None
        best_score_details = None
        highest_score = -1

        for candidate in candidates:
            score_details = score_candidate(
                ledger_record, candidate, self.date_tolerance_days
            )
            if score_details["total_score"] > highest_score:
                highest_score = score_details["total_score"]
                best_candidate = candidate
                best_score_details = score_details

        # Step 4: Find bank candidate
        bank_candidate = None
        if best_candidate:
            b_candidates = find_bank_candidates(best_candidate, bank_records)
            if b_candidates:
                bank_candidate = b_candidates[0]
        else:
            b_candidates = find_bank_candidates(ledger_record, bank_records)
            if b_candidates:
                bank_candidate = b_candidates[0]

        # Step 5-11: Classify result
        classification = classify_reconciliation_result(
            ledger_record=ledger_record,
            best_candidate=best_candidate,
            score_details=best_score_details,
            candidate_count=len(candidates),
            bank_candidate=bank_candidate
        )

        # Step 12: Generate structured evidence
        if best_score_details:
            amount_res = best_score_details["amount_res"]
            date_res = best_score_details["date_res"]
            exact_res = best_score_details["exact_res"]
            ref_sim = best_score_details["ref_similarity"]

            evidence = Evidence(
                payment_id_match=exact_res["payment_id_match"],
                reference_similarity=ref_sim,
                ledger_amount_paise=amount_res["ledger_expected_net"],
                settlement_amount_paise=best_candidate.get("net_amount", 0) if best_candidate else None,
                bank_amount_paise=bank_candidate.get("amount", 0) if bank_candidate else None,
                amount_difference_paise=amount_res["net_difference"],
                fee_difference_paise=amount_res["fee_difference"],
                tax_difference_paise=amount_res["tax_difference"],
                date_difference_days=date_res.get("difference_days", 0),
                duplicate_candidates_count=len(candidates),
                explanation=(
                    f"Match status: {classification['match_status']}. "
                    f"Payment ID exact: {exact_res['payment_id_match']}, Ref sim: {ref_sim:.2f}, "
                    f"Amount diff: INR {amount_res['net_difference']/100:.2f}, Date diff: {date_res.get('difference_days', 0)} days."
                )
            )
            score_breakdown = best_score_details["score_breakdown"]
        else:
            evidence = Evidence(
                payment_id_match=False,
                reference_similarity=0.0,
                ledger_amount_paise=ledger_record.get("expected_settlement", ledger_record.get("amount", 0)),
                settlement_amount_paise=None,
                bank_amount_paise=bank_candidate.get("amount", 0) if bank_candidate else None,
                amount_difference_paise=ledger_record.get("expected_settlement", 0),
                fee_difference_paise=0,
                tax_difference_paise=0,
                date_difference_days=0,
                duplicate_candidates_count=len(candidates),
                explanation=f"No matching settlement candidate found for payment {ledger_record.get('payment_id')}."
            )
            score_breakdown = ScoreBreakdown()

        elapsed_ms = (time.time() - start_time) * 1000.0

        if classification["matched"] and best_candidate:
            matched_settlement_ids.add(best_candidate.get("settlement_id"))

        result = ReconciliationResult(
            run_id=run_id,
            transaction_id=ledger_record.get("transaction_id"),
            matched=classification["matched"],
            match_status=classification["match_status"],
            confidence=classification["confidence"],
            matched_settlement_id=best_candidate.get("settlement_id") if best_candidate else None,
            matched_bank_transaction_id=bank_candidate.get("bank_transaction_id") if bank_candidate else None,
            reason_code=classification["reason_code"],
            score_breakdown=score_breakdown,
            evidence=evidence,
            financial_difference_paise=classification["financial_difference_paise"],
            processing_time_ms=round(elapsed_ms, 2),
            engine_version=self.engine_version,
            created_at=datetime.utcnow()
        )

        return result
