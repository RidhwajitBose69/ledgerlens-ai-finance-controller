import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.db.mongo import connect_db, close_db, db_container
from backend.app.api.v1.endpoints.reconciliation import router as reconciliation_router
from backend.app.api.v1.endpoints.exceptions import router as exceptions_router
from backend.app.api.v1.endpoints.evaluation import router as evaluation_router
from backend.app.api.v1.endpoints.analytics import router as analytics_router
from backend.app.api.v1.endpoints.agent import router as agent_router
from backend.app.api.v1.endpoints.audit import router as audit_router
from backend.app.api.v1.endpoints.data import router as data_router
from backend.app.api.v1.endpoints.integrations import router as integrations_router

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger("ledgerlens")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()

app = FastAPI(
    title="LedgerLens API",
    description="AI Finance Controller for Autonomous Settlement Reconciliation",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    db_status = "connected" if db_container.db is not None else "disconnected"
    return {
        "status": "ok",
        "database": db_status,
        "version": "1.0.0"
    }

app.include_router(reconciliation_router, prefix="/api/v1")
app.include_router(exceptions_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")

# Serve Frontend Application
app.mount("/", StaticFiles(directory="frontend/public", html=True), name="static")
