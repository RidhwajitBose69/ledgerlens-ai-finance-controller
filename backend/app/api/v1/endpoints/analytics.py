from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from backend.app.db.mongo import db_container
from backend.app.analytics.root_cause_service import analyze_root_causes
from backend.app.analytics.clustering import cluster_exceptions
from backend.app.analytics.batch_anomaly import detect_batch_anomalies

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/root-causes/{run_id}", response_model=Dict[str, Any])
async def get_root_causes(run_id: str):
    exp_cursor = db_container.db.exceptions.find({"run_id": run_id}, {"_id": 0})
    exceptions = await exp_cursor.to_list(length=10000)

    tx_cursor = db_container.db.transactions.find({}, {"_id": 0})
    transactions = await tx_cursor.to_list(length=10000)

    root_causes = analyze_root_causes(exceptions, transactions)
    clusters = cluster_exceptions(exceptions)

    return {
        "run_id": run_id,
        "total_exceptions": len(exceptions),
        "root_causes": root_causes,
        "clusters": clusters
    }

@router.get("/exceptions/{run_id}", response_model=Dict[str, Any])
async def get_exception_analytics(run_id: str):
    exp_cursor = db_container.db.exceptions.find({"run_id": run_id}, {"_id": 0})
    exceptions = await exp_cursor.to_list(length=10000)

    results_cursor = db_container.db.reconciliation_results.find({"run_id": run_id}, {"_id": 0})
    results = await results_cursor.to_list(length=10000)

    settlements_cursor = db_container.db.settlements.find({}, {"_id": 0})
    settlements = await settlements_cursor.to_list(length=10000)

    batch_anomalies = detect_batch_anomalies(results, settlements)

    by_reason: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total_financial_impact = 0

    for exp in exceptions:
        rc = exp.get("reason_code", "UNKNOWN")
        prio = exp.get("priority", "LOW")
        st = exp.get("status", "DETECTED")
        impact = exp.get("financial_impact_paise", 0)

        by_reason[rc] = by_reason.get(rc, 0) + 1
        by_priority[prio] = by_priority.get(prio, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        total_financial_impact += impact

    return {
        "run_id": run_id,
        "total_exceptions": len(exceptions),
        "total_financial_impact_inr": round(total_financial_impact / 100.0, 2),
        "by_reason": by_reason,
        "by_priority": by_priority,
        "by_status": by_status,
        "batch_anomalies": batch_anomalies
    }
