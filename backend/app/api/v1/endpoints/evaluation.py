from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.app.db.mongo import db_container

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.get("/compare", response_model=Dict[str, Any])
async def compare_runs(run_a: str = Query(...), run_b: str = Query(...)):
    eval_a = await db_container.db.evaluation_results.find_one({"run_id": run_a}, {"_id": 0})
    eval_b = await db_container.db.evaluation_results.find_one({"run_id": run_b}, {"_id": 0})

    if not eval_a or not eval_b:
        raise HTTPException(status_code=404, detail="One or both evaluation runs not found")

    ma = eval_a["metrics"]
    mb = eval_b["metrics"]

    comparison = {
        "run_a_id": run_a,
        "run_b_id": run_b,
        "metrics_diff": {
            "accuracy": round(mb["accuracy"] - ma["accuracy"], 4),
            "precision": round(mb["precision"] - ma["precision"], 4),
            "recall": round(mb["recall"] - ma["recall"], 4),
            "f1": round(mb["f1"] - ma["f1"], 4),
            "false_match_rate": round(mb["false_match_rate"] - ma["false_match_rate"], 4),
            "amount_reconciliation_rate": round(mb["amount_reconciliation_rate"] - ma["amount_reconciliation_rate"], 4),
            "throughput_records_per_sec": round(mb["throughput_records_per_sec"] - ma["throughput_records_per_sec"], 2),
            "avg_latency_ms": round(mb["avg_latency_ms"] - ma["avg_latency_ms"], 2)
        },
        "run_a": eval_a,
        "run_b": eval_b
    }

    return comparison

@router.get("/{run_id}", response_model=Dict[str, Any])
async def get_evaluation_results(run_id: str):
    eval_res = await db_container.db.evaluation_results.find_one({"run_id": run_id}, {"_id": 0})
    if not eval_res:
        # Check if run exists and calculate on the fly
        run_info = await db_container.db.reconciliation_runs.find_one({"run_id": run_id}, {"_id": 0})
        if not run_info:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Load results from Mongo
        results_cursor = db_container.db.reconciliation_results.find({"run_id": run_id}, {"_id": 0})
        results = await results_cursor.to_list(length=10000)

        # Load ground truth from Mongo or file
        gt_cursor = db_container.db.ground_truth.find({}, {"_id": 0})
        ground_truth = await gt_cursor.to_list(length=10000)

        if not ground_truth:
            import json, os
            gt_path = "data/ground_truth/ground_truth.json"
            if os.path.exists(gt_path):
                with open(gt_path, "r") as f:
                    ground_truth = json.load(f)

        from backend.app.evaluation.metrics import compute_evaluation_metrics
        from backend.app.evaluation.confusion_matrix import generate_confusion_matrix

        metrics = compute_evaluation_metrics(results, ground_truth, run_info)
        cm = generate_confusion_matrix(results, ground_truth)

        eval_res = {
            "run_id": run_id,
            "metrics": metrics,
            "confusion_matrix": cm,
            "dataset_records": len(results),
            "created_at": run_info.get("completed_at")
        }
        await db_container.db.evaluation_results.update_one({"run_id": run_id}, {"$set": eval_res}, upsert=True)

    return eval_res
