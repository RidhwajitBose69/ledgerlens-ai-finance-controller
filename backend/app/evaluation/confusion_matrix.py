from typing import List, Dict, Any

def generate_confusion_matrix(results: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> Dict[str, Any]:
    gt_map = {gt["transaction_id"]: gt for gt in ground_truth}
    labels = [
        "MATCHED", "FEE_VARIANCE", "TAX_VARIANCE", "DATE_VARIANCE",
        "PARTIAL_SETTLEMENT", "DUPLICATE", "MISSING_SETTLEMENT",
        "MISSING_LEDGER", "REFERENCE_MISMATCH", "UNKNOWN_TRANSACTION",
        "CURRENCY_MISMATCH", "REVERSED_TRANSACTION"
    ]

    matrix: Dict[str, Dict[str, int]] = {row: {col: 0 for col in labels} for row in labels}

    for res in results:
        gt = gt_map.get(res["transaction_id"])
        if not gt:
            continue

        actual = gt["true_match_status"]
        predicted = res["match_status"]

        if actual not in matrix:
            actual = "MATCHED"
        if predicted not in matrix[actual]:
            predicted = "MATCHED"

        matrix[actual][predicted] += 1

    return {
        "labels": labels,
        "matrix": matrix
    }
