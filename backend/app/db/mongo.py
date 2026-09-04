import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient, ASCENDING, DESCENDING
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db_container = MongoDB()

def get_sync_db():
    sync_client = MongoClient(settings.MONGODB_URI)
    return sync_client[settings.MONGODB_DATABASE]

async def connect_db():
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}")
    db_container.client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_container.db = db_container.client[settings.MONGODB_DATABASE]
    await init_indexes(db_container.db)
    logger.info("MongoDB connected and indexes initialized.")

async def close_db():
    if db_container.client:
        db_container.client.close()
        logger.info("MongoDB connection closed.")

async def init_indexes(db: AsyncIOMotorDatabase):
    # transactions indexes
    await db.transactions.create_index([("transaction_id", ASCENDING)], unique=True)
    await db.transactions.create_index([("payment_id", ASCENDING)])
    await db.transactions.create_index([("order_id", ASCENDING)])
    await db.transactions.create_index([("reference_id", ASCENDING)])
    await db.transactions.create_index([("status", ASCENDING)])

    # settlements indexes
    await db.settlements.create_index([("settlement_id", ASCENDING)], unique=True)
    await db.settlements.create_index([("payment_id", ASCENDING)])
    await db.settlements.create_index([("reference_id", ASCENDING)])
    await db.settlements.create_index([("utr", ASCENDING)])

    # bank_transactions indexes
    await db.bank_transactions.create_index([("bank_transaction_id", ASCENDING)], unique=True)
    await db.bank_transactions.create_index([("reference_id", ASCENDING)])
    await db.bank_transactions.create_index([("utr", ASCENDING)])

    # reconciliation_runs indexes
    await db.reconciliation_runs.create_index([("run_id", ASCENDING)], unique=True)
    await db.reconciliation_runs.create_index([("created_at", DESCENDING)])

    # reconciliation_results indexes
    await db.reconciliation_results.create_index([("run_id", ASCENDING), ("transaction_id", ASCENDING)], unique=True)
    await db.reconciliation_results.create_index([("run_id", ASCENDING)])
    await db.reconciliation_results.create_index([("match_status", ASCENDING)])
    await db.reconciliation_results.create_index([("reason_code", ASCENDING)])

    # exceptions indexes
    await db.exceptions.create_index([("exception_id", ASCENDING)], unique=True)
    await db.exceptions.create_index([("run_id", ASCENDING)])
    await db.exceptions.create_index([("transaction_id", ASCENDING)])
    await db.exceptions.create_index([("status", ASCENDING)])
    await db.exceptions.create_index([("priority", ASCENDING)])
    await db.exceptions.create_index([("reason_code", ASCENDING)])

    # agent_investigations indexes
    await db.agent_investigations.create_index([("investigation_id", ASCENDING)], unique=True)
    await db.agent_investigations.create_index([("exception_id", ASCENDING)])

    # audit_logs indexes
    await db.audit_logs.create_index([("audit_id", ASCENDING)], unique=True)
    await db.audit_logs.create_index([("run_id", ASCENDING)])
    await db.audit_logs.create_index([("transaction_id", ASCENDING)])
    await db.audit_logs.create_index([("timestamp", DESCENDING)])

    # evaluation_results indexes
    await db.evaluation_results.create_index([("run_id", ASCENDING)], unique=True)
