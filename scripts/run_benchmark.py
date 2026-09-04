import time
import os
import sys
import json
import psutil
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.reconciliation.engine import ReconciliationEngine
from scripts.generate_dataset import generate_dataset

def benchmark_dataset(records_count: int, seed: int = 42) -> dict:
    generate_dataset(records_count=records_count, seed=seed, output_dir=f"data/benchmark_{records_count}")

    with open(f"data/benchmark_{records_count}/ledger.json", "r") as f:
        transactions = json.load(f)
    with open(f"data/benchmark_{records_count}/settlements.json", "r") as f:
        settlements = json.load(f)
    with open(f"data/benchmark_{records_count}/bank_transactions.json", "r") as f:
        bank_records = json.load(f)

    engine = ReconciliationEngine(date_tolerance_days=3)
    matched_ids = set()

    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)

    start_time = time.time()
    results = []

    for tx in transactions:
        res = engine.reconcile_transaction(
            ledger_record=tx,
            settlements=settlements,
            bank_records=bank_records,
            matched_settlement_ids=matched_ids,
            run_id=f"BM_{records_count}"
        )
        results.append(res)

    total_time_s = time.time() - start_time
    mem_after = process.memory_info().rss / (1024 * 1024)

    throughput = records_count / total_time_s if total_time_s > 0 else 0.0
    avg_latency_ms = (total_time_s * 1000.0) / records_count if records_count > 0 else 0.0

    return {
        "records_count": records_count,
        "total_time_seconds": round(total_time_s, 4),
        "throughput_records_per_sec": round(throughput, 2),
        "avg_latency_per_record_ms": round(avg_latency_ms, 3),
        "memory_before_mb": round(mem_before, 2),
        "memory_after_mb": round(mem_after, 2),
        "memory_delta_mb": round(mem_after - mem_before, 2)
    }

def main():
    print("=====================================================")
    print("      LedgerLens Reconciliation Engine Benchmark     ")
    print("=====================================================")

    scales = [100, 500, 1000]
    benchmarks = []

    for scale in scales:
        print(f"Benchmarking {scale} records dataset...")
        res = benchmark_dataset(scale)
        benchmarks.append(res)
        print(f"  Result: {res['throughput_records_per_sec']} rec/s | Avg Latency: {res['avg_latency_per_record_ms']} ms | Memory Delta: {res['memory_delta_mb']} MB")

    os.makedirs("docs/benchmarks", exist_ok=True)
    with open("docs/benchmarks/benchmark_results.json", "w") as f:
        json.dump(benchmarks, f, indent=2)

    md_report = f"""# LedgerLens Reconciliation Engine Benchmark Report

Generated at: {datetime.now(timezone.utc).isoformat()}

## Performance Scaling

| Scale (Records) | Total Time (s) | Throughput (rec/s) | Avg Latency (ms/rec) | Memory Used (MB) |
|:---:|:---:|:---:|:---:|:---:|
"""
    for b in benchmarks:
        md_report += f"| {b['records_count']} | {b['total_time_seconds']} | {b['throughput_records_per_sec']} | {b['avg_latency_per_record_ms']} | {b['memory_delta_mb']} |\n"

    with open("docs/benchmarks/benchmark_report.md", "w") as f:
        f.write(md_report)

    print("\nBenchmark completed. Report written to docs/benchmarks/benchmark_report.md")

if __name__ == "__main__":
    main()
