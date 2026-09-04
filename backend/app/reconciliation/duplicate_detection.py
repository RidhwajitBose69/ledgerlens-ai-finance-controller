from typing import List, Dict, Any

def check_duplicates(
    settlement_candidates: List[Dict[str, Any]],
    matched_settlement_ids: set
) -> Dict[str, Any]:
    dup_count = len(settlement_candidates)
    has_already_settled_candidate = any(s.get("settlement_id") in matched_settlement_ids for s in settlement_candidates)

    return {
        "candidate_count": dup_count,
        "is_duplicate_candidate": dup_count > 1 or has_already_settled_candidate,
        "has_already_settled": has_already_settled_candidate
    }
