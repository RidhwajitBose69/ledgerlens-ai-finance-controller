import numpy as np
from typing import List, Dict, Any

def detect_batch_anomalies(
    results: List[Dict[str, Any]],
    settlements: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    s_map = {s.get("settlement_id"): s for s in settlements if s.get("settlement_id")}

    # Group by settlement date (batch)
    batches: Dict[str, Dict[str, Any]] = {}

    for res in results:
        s_id = res.get("matched_settlement_id")
        batch_key = "Unmatched Batch"
        if s_id and s_id in s_map:
            date_str = s_map[s_id].get("settlement_date", "")[:10]
            if date_str:
                batch_key = f"Batch {date_str}"

        if batch_key not in batches:
            batches[batch_key] = {"batch_id": batch_key, "total": 0, "exceptions": 0, "matched": 0, "impact_paise": 0}

        batches[batch_key]["total"] += 1
        if res.get("matched"):
            batches[batch_key]["matched"] += 1
        else:
            batches[batch_key]["exceptions"] += 1
            batches[batch_key]["impact_paise"] += res.get("financial_difference_paise", 0)

    rates = []
    batch_list = list(batches.values())
    for b in batch_list:
        rate = b["exceptions"] / b["total"] if b["total"] > 0 else 0.0
        b["exception_rate"] = round(rate, 4)
        rates.append(rate)

    if not rates:
        return []

    arr = np.array(rates)
    mean = np.mean(arr)
    std = np.std(arr)

    anomalies = []
    for b in batch_list:
        z_score = (b["exception_rate"] - mean) / std if std > 0 else 0.0
        is_anomalous = z_score >= 1.5 or b["exception_rate"] >= 0.35

        b["z_score"] = round(float(z_score), 2)
        b["is_anomalous"] = is_anomalous
        b["impact_inr"] = round(b["impact_paise"] / 100.0, 2)
        if is_anomalous:
            anomalies.append(b)

    batch_list.sort(key=lambda x: x["exception_rate"], reverse=True)
    return batch_list
