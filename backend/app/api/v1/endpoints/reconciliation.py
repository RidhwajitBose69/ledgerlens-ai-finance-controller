import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from backend.app.db.mongo import db_container
from backend.app.schemas.domain import ReconciliationRun, ReconciliationRunOptions
from backend.app.services.reconciliation_service import execute_reconciliation_run

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])

@router.post("/runs", response_model=Dict[str, Any])
async def create_reconciliation_run(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    dataset_id = payload.get("dataset_id", "demo-500")
    options = payload.get("options", {})

    active_run = await db_container.db.reconciliation_runs.find_one(
        {"status": {"$in": ["queued", "processing"]}}, {"_id": 0}
    )
    if active_run:
        raise HTTPException(status_code=409, detail=f"A reconciliation run ({active_run.get('run_id')}) is already in progress.")

    run_id = f"RUN_{uuid.uuid4().hex[:8].upper()}"

    doc = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "queued",
        "options": options,
        "total_records": 0,
        "processed_records": 0,
        "matched_count": 0,
        "exception_count": 0,
        "auto_resolved_count": 0,
        "human_review_count": 0,
        "unresolved_count": 0,
        "reconciled_amount_paise": 0,
        "unreconciled_amount_paise": 0,
        "total_processing_time_ms": 0.0,
        "engine_version": "reconciliation-engine-v1.0",
        "created_at": datetime.now(timezone.utc)
    }

    await db_container.db.reconciliation_runs.insert_one(doc)

    background_tasks.add_task(execute_reconciliation_run, run_id, dataset_id, options)

    return {"run_id": run_id, "status": "queued"}

@router.get("/runs", response_model=List[Dict[str, Any]])
async def list_reconciliation_runs(limit: int = 20):
    cursor = db_container.db.reconciliation_runs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)

@router.get("/runs/{run_id}", response_model=Dict[str, Any])
async def get_run_status(run_id: str):
    run = await db_container.db.reconciliation_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run

@router.get("/runs/{run_id}/results", response_model=Dict[str, Any])
async def get_run_results(
    run_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    reason_code: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None
):
    query: Dict[str, Any] = {"run_id": run_id}
    if status:
        query["match_status"] = status
    if reason_code:
        query["reason_code"] = reason_code
    if min_confidence is not None:
        query["confidence"] = {"$gte": min_confidence}
    if max_confidence is not None:
        query.setdefault("confidence", {})["$lte"] = max_confidence

    skip = (page - 1) * limit
    total = await db_container.db.reconciliation_results.count_documents(query)
    cursor = db_container.db.reconciliation_results.find(query, {"_id": 0}).skip(skip).limit(limit)
    results = await cursor.to_list(length=limit)

    return {
        "run_id": run_id,
        "total": total,
        "page": page,
        "limit": limit,
        "results": results
    }

@router.get("/compare", response_model=Dict[str, Any])
async def compare_runs(
    run_a: str = Query(..., description="Run ID A"),
    run_b: str = Query(..., description="Run ID B")
):
    run1 = await db_container.db.reconciliation_runs.find_one({"run_id": run_a}, {"_id": 0})
    run2 = await db_container.db.reconciliation_runs.find_one({"run_id": run_b}, {"_id": 0})

    if not run1 or not run2:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    def calc_match_rate(run):
        return (run.get("matched_count", 0) / run.get("total_records", 1)) * 100 if run.get("total_records") else 0

    return {
        "run_a": run1,
        "run_b": run2,
        "comparison": {
            "match_rate_change": calc_match_rate(run2) - calc_match_rate(run1),
            "exception_change": run2.get("exception_count", 0) - run1.get("exception_count", 0),
            "exposure_change": run2.get("unreconciled_amount_paise", 0) - run1.get("unreconciled_amount_paise", 0),
            "throughput_change": (run2.get("processed_records", 0) / (run2.get("total_processing_time_ms", 1)/1000.0) if run2.get("total_processing_time_ms") else 0) - (run1.get("processed_records", 0) / (run1.get("total_processing_time_ms", 1)/1000.0) if run1.get("total_processing_time_ms") else 0)
        }
    }
