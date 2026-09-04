from typing import Dict, Any
from backend.app.agents.providers.base import BaseLLMProvider

class MockAIProvider(BaseLLMProvider):
    def name(self) -> str:
        return "MOCK"

    async def investigate_exception(
        self,
        exception: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        reason = exception.get("reason_code", "UNKNOWN")
        financial_impact = exception.get("financial_impact_paise", 0)
        tx = context_data.get("transaction") or {}
        st = context_data.get("settlement") or {}
        evidence_dict = exception.get("evidence") or {}

        evidence_items = [
            f"Retrieved internal ledger record for transaction {tx.get('transaction_id')}",
            f"Retrieved gateway settlement record {st.get('settlement_id') if st else 'None'}",
            f"Evaluated amount difference: INR {financial_impact / 100.0:.2f}"
        ]

        tool_calls = [
            {"tool": "get_transaction", "args": {"transaction_id": tx.get("transaction_id")}, "status": "success"},
            {"tool": "get_settlement", "args": {"settlement_id": st.get("settlement_id")}, "status": "success"},
            {"tool": "check_fees", "args": {"transaction_id": tx.get("transaction_id")}, "status": "success"}
        ]

        if reason in ["FEE_VARIANCE", "TAX_VARIANCE", "DATE_VARIANCE"]:
            decision = "AUTO_RESOLVE"
            confidence = 0.96
            risk_level = "LOW"
            summary = (
                f"Autonomous AI Investigation confirmed {reason.replace('_', ' ').lower()} "
                f"of INR {financial_impact / 100.0:.2f}. The variance is within permissible automated settlement policy thresholds."
            )
            recommended_action = "AUTO_RESOLVE_FEE_ADJUSTMENT" if reason == "FEE_VARIANCE" else "AUTO_RESOLVE_TAX_ADJUSTMENT"
        elif reason in ["DUPLICATE", "MULTIPLE_CANDIDATES"]:
            decision = "HUMAN_REVIEW"
            confidence = 0.85
            risk_level = "HIGH"
            summary = (
                f"Potential duplicate settlement records detected ({evidence_dict.get('duplicate_candidates_count', 2)} candidates). "
                f"Requires human finance operations review to prevent double payout."
            )
            recommended_action = "ESCALATE_HUMAN_DUPLICATE_CHECK"
        else:
            decision = "HUMAN_REVIEW"

            # Confidence is reason-specific and reflects the strength of
            # evidence available to the controller. The 95% policy gate
            # remains unchanged, so these cases still require human review.
            confidence_by_reason = {
                "MISSING_SETTLEMENT": 0.78,
                "MISSING_LEDGER": 0.82,
                "PARTIAL_SETTLEMENT": 0.78,
                "UNKNOWN_TRANSACTION": 0.72,
                "REFERENCE_MISMATCH": 0.74,
                "CURRENCY_MISMATCH": 0.91,
                "REVERSED_TRANSACTION": 0.88,
                "AMOUNT_MISMATCH": 0.76,
                "FAILED_PAYMENT": 0.86
            }

            confidence = confidence_by_reason.get(reason, 0.75)
            risk_level = "HIGH" if financial_impact > 100000 else "MEDIUM"

            summary = (
                f"Discrepancy '{reason}' involving INR {financial_impact / 100.0:.2f} "
                f"requires human review. Evidence is insufficient for safe "
                f"autonomous resolution under active risk policies."
            )

            recommended_action = "MANUAL_RECONCILIATION_VERIFICATION"

        return {
            "decision": decision,
            "confidence": confidence,
            "reason_code": reason,
            "summary": summary,
            "evidence_items": evidence_items,
            "tool_calls": tool_calls,
            "recommended_action": recommended_action,
            "risk_level": risk_level,
            "financial_impact_paise": financial_impact
        }
