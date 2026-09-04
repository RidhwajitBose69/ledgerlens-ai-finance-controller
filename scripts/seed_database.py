import json
import os
import sys
from pymongo import MongoClient

# Ensure app imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings

def seed_database(dataset_dir: str = "data/generated"):
    print(f"Connecting to MongoDB at {settings.MONGODB_URI} (Database: {settings.MONGODB_DATABASE})...")
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DATABASE]

    # Clean existing seed collections
    print("Clearing existing collections...")
    db.transactions.delete_many({})
    db.settlements.delete_many({})
    db.bank_transactions.delete_many({})

    # CRITICAL: Seed ledger.json (not transactions.json) as the transactions collection.
    # ledger.json uses the internal ledger schema: amount, recorded_fee, recorded_tax,
    # expected_settlement — which is what the reconciliation engine and API serialization expect.
    # transactions.json uses a canonical schema (gross_amount, net_amount) for analytics only.
    ledger_path = os.path.join(dataset_dir, "ledger.json")
    tx_path = os.path.join(dataset_dir, "transactions.json")
    # Use ledger.json if present; fall back to transactions.json with a warning
    if os.path.exists(ledger_path):
        actual_tx_path = ledger_path
    else:
        actual_tx_path = tx_path
        print("WARNING: ledger.json not found. Falling back to transactions.json — "
              "financial fields may be missing for no-candidate exceptions.")

    set_path = os.path.join(dataset_dir, "settlements.json")
    bank_path = os.path.join(dataset_dir, "bank_transactions.json")

    if not os.path.exists(actual_tx_path) or not os.path.exists(set_path) or not os.path.exists(bank_path):
        print(f"Error: Dataset files not found in {dataset_dir}. Run generate_dataset.py first.")
        sys.exit(1)

    with open(actual_tx_path, "r") as f:
        transactions = json.load(f)
    print(f"  Seeding transactions from: {os.path.basename(actual_tx_path)} ({len(transactions)} records)")

    with open(set_path, "r") as f:
        settlements = json.load(f)

    with open(bank_path, "r") as f:
        bank_transactions = json.load(f)

    if transactions:
        db.transactions.insert_many(transactions)
    if settlements:
        db.settlements.insert_many(settlements)
    if bank_transactions:
        db.bank_transactions.insert_many(bank_transactions)

    print(f"Successfully seeded MongoDB database '{settings.MONGODB_DATABASE}':")
    print(f"  - transactions: {db.transactions.count_documents({})}")
    print(f"  - settlements: {db.settlements.count_documents({})}")
    print(f"  - bank_transactions: {db.bank_transactions.count_documents({})}")

if __name__ == "__main__":
    seed_database()
