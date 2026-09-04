import numpy as np
from typing import List, Dict, Any

def compute_evaluation_metrics(
    results: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    run_info: Dict[str, Any]
) -> Dict[str, Any]:
    gt_map = {gt["transaction_id"]: gt for gt in ground_truth}

    tp = 0  # True Positives: system said MATCHED, GT said MATCHED
    fp = 0  # False Positives (False Matches): system said MATCHED, GT said Exception/Mismatch
    tn = 0  # True Negatives: system flagged Exception, GT said Exception/Mismatch
    fn = 0  # False Negatives: system flagged Exception, GT said MATCHED

    reconciled_amount = 0
    unreconciled_amount = 0
    total_gt_amount = 0

    latencies = []

    for res in results:
        tx_id = res["transaction_id"]
        gt = gt_map.get(tx_id)
        if not gt:
            continue

        latencies.append(res.get("processing_time_ms", 0.0))
        predicted_matched = res["matched"]
        actual_matched = (gt["true_match_status"] == "MATCHED")

        if res.get("evidence"):
            l_amt = res["evidence"].get("ledger_amount_paise", 0)
            total_gt_amount += l_amt
            if predicted_matched:
                reconciled_amount += l_amt
            else:
                unreconciled_amount += l_amt

        if predicted_matched and actual_matched:
            tp += 1
        elif predicted_matched and not actual_matched:
            fp += 1
        elif not predicted_matched and not actual_matched:
            tn += 1
        elif not predicted_matched and actual_matched:
            fn += 1

    total = len(results)
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    false_match_rate = fp / total if total > 0 else 0.0
    match_rate = (tp + fp) / total if total > 0 else 0.0

    total_time_s = run_info.get("total_processing_time_ms", 1.0) / 1000.0
    throughput = total / total_time_s if total_time_s > 0 else 0.0

    latencies_arr = np.array(latencies) if latencies else np.array([0])
    avg_latency = float(np.mean(latencies_arr))
    p50_latency = float(np.percentile(latencies_arr, 50))
    p95_latency = float(np.percentile(latencies_arr, 95))

    amount_reconciliation_rate = reconciled_amount / total_gt_amount if total_gt_amount > 0 else 0.0

    return {
        "total_records": total,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "match_rate": round(match_rate, 4),
        "false_match_rate": round(false_match_rate, 4),
        "amount_reconciliation_rate": round(amount_reconciliation_rate, 4),
        "reconciled_amount_inr": round(reconciled_amount / 100.0, 2),
        "unreconciled_amount_inr": round(unreconciled_amount / 100.0, 2),
        "throughput_records_per_sec": round(throughput, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "p50_latency_ms": round(p50_latency, 2),
        "p95_latency_ms": round(p95_latency, 2)
    }
