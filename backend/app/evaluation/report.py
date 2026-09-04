from typing import Dict, Any

def format_evaluation_report(metrics: Dict[str, Any], run_id: str) -> str:
    report = f"""
=====================================================
            LedgerLens Evaluation Report
=====================================================
Run ID: {run_id}
Total Records: {metrics['total_records']}

Accuracy:                      {metrics['accuracy']*100:.2f}%
Precision:                     {metrics['precision']*100:.2f}%
Recall:                        {metrics['recall']*100:.2f}%
F1 Score:                      {metrics['f1']*100:.2f}%

Match Rate:                    {metrics['match_rate']*100:.2f}%
False Match Rate:              {metrics['false_match_rate']*100:.2f}%
False Matches Count:           {metrics['false_positives']}

Amount Reconciled:             ₹{metrics['reconciled_amount_inr']:,.2f}
Unreconciled Amount:           ₹{metrics['unreconciled_amount_inr']:,.2f}
Amount Reconciliation Rate:    {metrics['amount_reconciliation_rate']*100:.2f}%

Throughput:                    {metrics['throughput_records_per_sec']:.1f} records/sec
Avg Processing Time:           {metrics['avg_latency_ms']:.2f} ms
P50 Latency:                   {metrics['p50_latency_ms']:.2f} ms
P95 Latency:                   {metrics['p95_latency_ms']:.2f} ms
=====================================================
"""
    return report
