import numpy as np
from typing import List, Dict, Any
from sklearn.cluster import KMeans

def cluster_exceptions(exceptions: List[Dict[str, Any]], n_clusters: int = 4) -> List[Dict[str, Any]]:
    if not exceptions:
        return []

    actual_k = min(n_clusters, len(exceptions))

    reason_map = {
        "FEE_VARIANCE": 1, "TAX_VARIANCE": 2, "DATE_VARIANCE": 3,
        "PARTIAL_SETTLEMENT": 4, "DUPLICATE": 5, "MISSING_SETTLEMENT": 6,
        "MISSING_LEDGER": 7, "REFERENCE_MISMATCH": 8, "UNKNOWN_TRANSACTION": 9,
        "CURRENCY_MISMATCH": 10, "REVERSED_TRANSACTION": 11, "AMOUNT_MISMATCH": 12
    }

    features = []
    for e in exceptions:
        r_val = reason_map.get(e.get("reason_code"), 0)
        impact = e.get("financial_impact_paise", 0) / 100.0  # in INR
        conf = e.get("confidence", 0.5)
        prio_score = e.get("priority_score", 50.0)
        features.append([r_val, impact, conf, prio_score])

    X = np.array(features)
    kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    clusters: Dict[int, List[Dict[str, Any]]] = {}
    for idx, cluster_id in enumerate(labels):
        clusters.setdefault(int(cluster_id), []).append(exceptions[idx])

    cluster_summaries = []
    for c_id, exp_list in clusters.items():
        total_impact = sum(e.get("financial_impact_paise", 0) for e in exp_list)
        reasons = {}
        for e in exp_list:
            rc = e.get("reason_code")
            reasons[rc] = reasons.get(rc, 0) + 1
        top_reason = max(reasons.items(), key=lambda x: x[1])[0] if reasons else "UNKNOWN"

        cluster_summaries.append({
            "cluster_id": c_id + 1,
            "name": f"Cluster #{c_id+1}: {top_reason.replace('_', ' ').title()}",
            "size": len(exp_list),
            "dominant_reason": top_reason,
            "total_financial_impact_inr": round(total_impact / 100.0, 2),
            "sample_exceptions": [e.get("exception_id") for e in exp_list[:5]]
        })

    return cluster_summaries
