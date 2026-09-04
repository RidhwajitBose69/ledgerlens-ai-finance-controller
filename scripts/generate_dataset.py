import argparse
import hashlib
import json
import math
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

INDIAN_FIRST_NAMES = ["Aarav", "Aditi", "Rohan", "Priya", "Vikram", "Ananya", "Rahul", "Kavya", "Siddharth", "Neha", "Amit", "Pooja", "Arjun", "Sneha", "Karan", "Divya", "Suresh", "Meera", "Rajesh", "Swati"]
INDIAN_LAST_NAMES = ["Sharma", "Verma", "Gupta", "Patel", "Mehta", "Reddy", "Nair", "Rao", "Joshi", "Kumar", "Singh", "Chawla", "Bhasin", "Deshmukh", "Iyer", "Chopra", "Kulkarni", "Mukherjee"]
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "emi"]

def calculate_sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def generate_utr(rng: random.Random) -> str:
    return f"UTR{rng.randint(100000000000, 999999999999)}"

def generate_reference(rng: random.Random, prefix: str = "REF") -> str:
    return f"{prefix}_{rng.randint(10000000, 99999999)}"

def generate_dataset(
    records_count: int = 500,
    seed: int = 42,
    start_date_str: str = "2026-01-01",
    exception_rate: float = 0.20,
    output_dir: str = "data/generated"
):
    rng = random.Random(seed)
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("data/ground_truth", exist_ok=True)

    transactions = []
    ledger_records = []
    settlement_records = []
    bank_records = []
    ground_truth_records = []

    # Distribution probabilities according to spec (approximate total 100%)
    categories = [
        ("EXACT_MATCH", 0.60),
        ("FEE_VARIANCE", 0.05),
        ("TAX_VARIANCE", 0.05),
        ("DATE_VARIANCE", 0.05),
        ("PARTIAL_SETTLEMENT", 0.05),
        ("DUPLICATE", 0.04),
        ("MISSING_SETTLEMENT", 0.04),
        ("MISSING_LEDGER", 0.03),
        ("REFERENCE_MISMATCH", 0.03),
        ("UNKNOWN_TRANSACTION", 0.02),
        ("CURRENCY_MISMATCH", 0.02),
        ("REVERSED_TRANSACTION", 0.02),
    ]

    cat_names, cat_weights = zip(*categories)

    for i in range(1, records_count + 1):
        txn_id = f"TXN_{1000 + i}"
        order_id = f"ORD_{8000 + i}"
        payment_id = f"pay_{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}{rng.randint(10000000, 99999999)}"
        cust_id = f"CUST_{rng.randint(100, 999)}"
        ref_id = generate_reference(rng)
        utr = generate_utr(rng)

        days_offset = rng.randint(0, 30)
        minutes_offset = rng.randint(0, 1439)
        txn_date = start_date + timedelta(days=days_offset, minutes=minutes_offset)
        settlement_date = txn_date + timedelta(days=rng.randint(1, 2))

        method = rng.choice(PAYMENT_METHODS)

        # Amounts in paise (INR 100 to 50,000)
        gross_rupees = rng.randint(100, 50000)
        gross_paise = gross_rupees * 100

        # Calculate standard fee & tax (e.g. 1.8% fee + 18% GST on fee)
        fee_rate = 0.018 if method in ["card", "netbanking"] else (0.005 if method == "upi" else 0.015)
        fee_paise = int(round(gross_paise * fee_rate))
        tax_paise = int(round(fee_paise * 0.18))
        net_paise = gross_paise - fee_paise - tax_paise

        # Pick variance category for this record
        category = rng.choices(cat_names, weights=cat_weights, k=1)[0]

        canonical_status = "captured"
        currency = "INR"

        # Defaults
        ledger_entry = {
            "transaction_id": txn_id,
            "order_id": order_id,
            "payment_id": payment_id,
            "customer_id": cust_id,
            "reference_id": ref_id,
            "transaction_date": txn_date.isoformat(),
            "amount": gross_paise,
            "currency": currency,
            "status": canonical_status,
            "payment_method": method,
            "recorded_fee": fee_paise,
            "recorded_tax": tax_paise,
            "expected_settlement": net_paise,
            "source": "ledger"
        }
        ledger_entry["raw_record_hash"] = calculate_sha256(json.dumps(ledger_entry, sort_keys=True))

        settlement_id = f"set_{90000 + i}"
        settlement_entry = {
            "settlement_id": settlement_id,
            "payment_id": payment_id,
            "reference_id": ref_id,
            "settlement_date": settlement_date.isoformat(),
            "settlement_amount": gross_paise,
            "fee": fee_paise,
            "tax": tax_paise,
            "net_amount": net_paise,
            "settlement_status": "processed",
            "utr": utr,
            "source": "settlement"
        }

        bank_txn_id = f"BANK_{5000 + i}"
        bank_entry = {
            "bank_transaction_id": bank_txn_id,
            "reference_id": ref_id,
            "transaction_date": settlement_date.isoformat(),
            "amount": net_paise,
            "description": f"Razorpay Settlement {utr}",
            "credit_debit": "credit",
            "bank_status": "cleared",
            "utr": utr,
            "source": "bank"
        }

        true_match_status = "MATCHED"
        true_reason_code = "EXACT_MATCH"
        expected_res = "AUTO_RESOLVE"
        expected_diff = 0

        # Apply specific scenario modifications
        if category == "EXACT_MATCH":
            true_match_status = "MATCHED"
            true_reason_code = "EXACT_MATCH"
            expected_res = "AUTO_RESOLVE"

        elif category == "FEE_VARIANCE":
            # Extra fee charged by gateway (+1500 paise / INR 15)
            extra_fee = 1500
            settlement_entry["fee"] += extra_fee
            settlement_entry["net_amount"] -= extra_fee
            bank_entry["amount"] -= extra_fee
            true_match_status = "FEE_VARIANCE"
            true_reason_code = "FEE_VARIANCE"
            expected_res = "AUTO_RESOLVE"  # Policy engine permits fee variance auto resolution
            expected_diff = extra_fee

        elif category == "TAX_VARIANCE":
            # Tax variance (+500 paise / INR 5)
            extra_tax = 500
            settlement_entry["tax"] += extra_tax
            settlement_entry["net_amount"] -= extra_tax
            bank_entry["amount"] -= extra_tax
            true_match_status = "TAX_VARIANCE"
            true_reason_code = "TAX_VARIANCE"
            expected_res = "AUTO_RESOLVE"
            expected_diff = extra_tax

        elif category == "DATE_VARIANCE":
            # Delayed settlement date (+6 days, exceeding 3 day tolerance)
            delayed_date = settlement_date + timedelta(days=6)
            settlement_entry["settlement_date"] = delayed_date.isoformat()
            bank_entry["transaction_date"] = delayed_date.isoformat()
            true_match_status = "DATE_VARIANCE"
            true_reason_code = "DATE_VARIANCE"
            expected_res = "AUTO_RESOLVE"

        elif category == "PARTIAL_SETTLEMENT":
            # Settlement only settled 60% of gross
            settled_net = int(round(net_paise * 0.6))
            settlement_entry["net_amount"] = settled_net
            bank_entry["amount"] = settled_net
            true_match_status = "PARTIAL_SETTLEMENT"
            true_reason_code = "PARTIAL_SETTLEMENT"
            expected_res = "HUMAN_REVIEW"
            expected_diff = net_paise - settled_net

        elif category == "DUPLICATE":
            # Duplicate settlement record emitted
            dup_settlement = dict(settlement_entry)
            dup_settlement["settlement_id"] = f"set_{99000 + i}"
            dup_settlement["raw_record_hash"] = calculate_sha256(json.dumps(dup_settlement, sort_keys=True))
            settlement_records.append(dup_settlement)

            true_match_status = "DUPLICATE"
            true_reason_code = "DUPLICATE"
            expected_res = "HUMAN_REVIEW"

        elif category == "MISSING_SETTLEMENT":
            # Record exists in ledger, but no settlement emitted
            settlement_entry = None
            bank_entry = None
            true_match_status = "MISSING_SETTLEMENT"
            true_reason_code = "MISSING_SETTLEMENT"
            expected_res = "HUMAN_REVIEW"
            expected_diff = net_paise

        elif category == "MISSING_LEDGER":
            # Exists in settlement & bank, missing in ledger
            ledger_entry = None
            true_match_status = "MISSING_LEDGER"
            true_reason_code = "MISSING_LEDGER"
            expected_res = "HUMAN_REVIEW"

        elif category == "REFERENCE_MISMATCH":
            # Typos/mismatch in settlement reference ID
            mismatched_ref = f"REF_ERR_{rng.randint(1000, 9999)}"
            settlement_entry["reference_id"] = mismatched_ref
            true_match_status = "REFERENCE_MISMATCH"
            true_reason_code = "REFERENCE_MISMATCH"
            expected_res = "HUMAN_REVIEW"

        elif category == "UNKNOWN_TRANSACTION":
            # Random unknown transaction in bank statement
            bank_entry["reference_id"] = f"UNKNOWN_{rng.randint(1000, 9999)}"
            bank_entry["utr"] = f"UTR_UNK_{rng.randint(1000, 9999)}"
            true_match_status = "UNKNOWN_TRANSACTION"
            true_reason_code = "UNKNOWN_TRANSACTION"
            expected_res = "HUMAN_REVIEW"

        elif category == "CURRENCY_MISMATCH":
            ledger_entry["currency"] = "USD"
            true_match_status = "CURRENCY_MISMATCH"
            true_reason_code = "CURRENCY_MISMATCH"
            expected_res = "HUMAN_REVIEW"

        elif category == "REVERSED_TRANSACTION":
            ledger_entry["status"] = "reversed"
            true_match_status = "REVERSED_TRANSACTION"
            true_reason_code = "REVERSED_TRANSACTION"
            expected_res = "HUMAN_REVIEW"

        # Hash updates
        if settlement_entry:
            settlement_entry["raw_record_hash"] = calculate_sha256(json.dumps(settlement_entry, sort_keys=True))
            settlement_records.append(settlement_entry)

        if bank_entry:
            bank_entry["raw_record_hash"] = calculate_sha256(json.dumps(bank_entry, sort_keys=True))
            bank_records.append(bank_entry)

        if ledger_entry:
            ledger_records.append(ledger_entry)

        # Canonical transaction record
        tx_record = {
            "transaction_id": txn_id,
            "order_id": order_id,
            "payment_id": payment_id,
            "customer_id": cust_id,
            "reference_id": ref_id,
            "transaction_date": txn_date.isoformat(),
            "settlement_date": settlement_date.isoformat() if settlement_entry else None,
            "gross_amount": gross_paise,
            "fee": fee_paise,
            "tax": tax_paise,
            "net_amount": net_paise,
            "currency": currency,
            "payment_method": method,
            "source": "synthetic",
            "status": canonical_status,
            "raw_record_hash": calculate_sha256(f"{txn_id}:{payment_id}:{ref_id}")
        }
        transactions.append(tx_record)

        # Ground Truth record
        gt_record = {
            "ground_truth_id": f"GT_{1000 + i}",
            "transaction_id": txn_id,
            "true_match_status": true_match_status,
            "true_settlement_id": settlement_id if settlement_entry else None,
            "true_bank_transaction_id": bank_txn_id if bank_entry else None,
            "true_reason_code": true_reason_code,
            "expected_resolution": expected_res,
            "expected_amount_difference": expected_diff
        }
        ground_truth_records.append(gt_record)

    # Save to files
    with open(f"{output_dir}/transactions.json", "w") as f:
        json.dump(transactions, f, indent=2)

    with open(f"{output_dir}/ledger.json", "w") as f:
        json.dump(ledger_records, f, indent=2)

    with open(f"{output_dir}/settlements.json", "w") as f:
        json.dump(settlement_records, f, indent=2)

    with open(f"{output_dir}/bank_transactions.json", "w") as f:
        json.dump(bank_records, f, indent=2)

    with open(f"{output_dir}/ground_truth.json", "w") as f:
        json.dump(ground_truth_records, f, indent=2)

    with open("data/ground_truth/ground_truth.json", "w") as f:
        json.dump(ground_truth_records, f, indent=2)

    print(f"Generated dataset with {records_count} records (seed {seed}):")
    print(f"  - Ledger records: {len(ledger_records)}")
    print(f"  - Settlement records: {len(settlement_records)}")
    print(f"  - Bank records: {len(bank_records)}")
    print(f"  - Ground truth records: {len(ground_truth_records)}")
    print(f"Saved dataset artifacts to {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LedgerLens Dataset Generator")
    parser.add_argument("--records", type=int, default=500, help="Number of records to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--start-date", type=str, default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--exception-rate", type=float, default=0.20, help="Target exception rate")
    parser.add_argument("--output-dir", type=str, default="data/generated", help="Output directory")

    args = parser.parse_args()
    generate_dataset(
        records_count=args.records,
        seed=args.seed,
        start_date_str=args.start_date,
        exception_rate=args.exception_rate,
        output_dir=args.output_dir
    )
