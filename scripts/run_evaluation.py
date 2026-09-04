import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.services.reconciliation_service import execute_reconciliation_run
from backend.app.evaluation.metrics import compute_evaluation_metrics
from backend.app.evaluation.confusion_matrix import generate_confusion_matrix
from backend.app.evaluation.report import format_evaluation_report

def run_evaluation(records: int = 500, seed: int = 42):
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DATABASE]

    # Check if dataset and ground truth exist
    gt_path = "data/ground_truth/ground_truth.json"
    if not os.path.exists(gt_path):
        print("Ground truth dataset missing. Generating new dataset...")
        os.system(f"python scripts/generate_dataset.py --records {records} --seed {seed}")
        os.system("python scripts/seed_database.py")

    with open(gt_path, "r") as f:
        ground_truth = json.load(f)

    run_id = f"RUN_EVAL_{seed}_{uuid.uuid4().hex[:6]}"
    print(f"Triggering evaluation reconciliation run: {run_id} ({records} records)...")

    execute_reconciliation_run(run_id=run_id, dataset_id=f"demo-{records}")

    run_info = db.reconciliation_runs.find_one({"run_id": run_id})
    results = list(db.reconciliation_results.find({"run_id": run_id}))

    metrics = compute_evaluation_metrics(results, ground_truth, run_info)
    cm = generate_confusion_matrix(results, ground_truth)

    eval_doc = {
        "run_id": run_id,
        "metrics": metrics,
        "confusion_matrix": cm,
        "dataset_records": records,
        "dataset_seed": seed,
        "created_at": datetime.now(timezone.utc)
    }

    db.evaluation_results.update_one({"run_id": run_id}, {"$set": eval_doc}, upsert=True)

    report_text = format_evaluation_report(metrics, run_id)
    print(report_text)

    # Save to data directory for traceability
    os.makedirs("docs/evaluation", exist_ok=True)
    with open("docs/evaluation/latest_evaluation.json", "w") as f:
        json.dump(eval_doc, f, indent=2, default=str)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LedgerLens Evaluation CLI")
    parser.add_argument("--records", type=int, default=500, help="Records count")
    parser.add_argument("--seed", type=int, default=42, help="Seed")

    args = parser.parse_args()
    run_evaluation(records=args.records, seed=args.seed)
