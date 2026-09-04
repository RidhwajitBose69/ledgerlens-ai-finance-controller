from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class CanonicalTransaction(BaseModel):
    transaction_id: str
    order_id: str
    payment_id: str
    customer_id: str
    reference_id: str

    transaction_date: datetime
    settlement_date: Optional[datetime] = None

    gross_amount: int  # in paise
    fee: int  # in paise
    tax: int  # in paise
    net_amount: int  # in paise

    currency: str = "INR"
    payment_method: str  # upi, card, netbanking, wallet, emi

    source: str  # ledger, settlement, bank, razorpay
    status: str  # captured, settled, failed, reversed

    raw_record_hash: Optional[str] = None
    source_record_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LedgerRecord(BaseModel):
    transaction_id: str
    order_id: str
    payment_id: str
    customer_id: str
    reference_id: str
    transaction_date: datetime
    amount: int  # gross amount in paise
    currency: str = "INR"
    status: str
    payment_method: str
    recorded_fee: int  # in paise
    recorded_tax: int  # in paise
    expected_settlement: int  # net amount in paise
    source: str = "ledger"
    raw_record_hash: str

class SettlementRecord(BaseModel):
    settlement_id: str
    payment_id: str
    reference_id: str
    settlement_date: datetime
    settlement_amount: int  # gross in paise
    fee: int  # in paise
    tax: int  # in paise
    net_amount: int  # in paise
    settlement_status: str  # processed, failed
    utr: str
    source: str = "settlement"
    raw_record_hash: str

class BankRecord(BaseModel):
    bank_transaction_id: str
    reference_id: str
    transaction_date: datetime
    amount: int  # net in paise
    description: str
    credit_debit: str  # credit, debit
    bank_status: str  # cleared
    utr: str
    source: str = "bank"
    raw_record_hash: str

class GroundTruthRecord(BaseModel):
    ground_truth_id: str
    transaction_id: str
    true_match_status: str  # MATCHED, FEE_VARIANCE, TAX_VARIANCE, AMOUNT_MISMATCH, etc.
    true_settlement_id: Optional[str] = None
    true_bank_transaction_id: Optional[str] = None
    true_reason_code: str
    expected_resolution: str  # AUTO_RESOLVE, HUMAN_REVIEW, UNRESOLVED
    expected_amount_difference: int = 0  # in paise

class ReconciliationRunOptions(BaseModel):
    date_tolerance_days: int = 3
    auto_resolution_threshold: float = 0.95
    max_auto_resolution_amount: int = 10000000  # 100,000 INR in paise

class ReconciliationRun(BaseModel):
    run_id: str
    dataset_id: str = "demo-500"
    status: str = "queued"  # queued, processing, completed, failed
    options: ReconciliationRunOptions = Field(default_factory=ReconciliationRunOptions)
    total_records: int = 0
    processed_records: int = 0
    matched_count: int = 0
    exception_count: int = 0
    auto_resolved_count: int = 0
    human_review_count: int = 0
    unresolved_count: int = 0
    reconciled_amount_paise: int = 0
    unreconciled_amount_paise: int = 0
    total_processing_time_ms: float = 0.0
    engine_version: str = "reconciliation-engine-v1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class ScoreBreakdown(BaseModel):
    payment_id_exact: int = 0
    reference_exact: int = 0
    reference_fuzzy_score: float = 0.0
    order_id_exact: int = 0
    amount_compatible: int = 0
    date_compatible: int = 0
    customer_compatible: int = 0
    total_score: int = 0

class Evidence(BaseModel):
    payment_id_match: bool = False
    reference_similarity: float = 0.0
    ledger_amount_paise: int = 0
    settlement_amount_paise: Optional[int] = None
    bank_amount_paise: Optional[int] = None
    amount_difference_paise: int = 0
    fee_difference_paise: int = 0
    tax_difference_paise: int = 0
    date_difference_days: int = 0
    duplicate_candidates_count: int = 0
    explanation: str = ""

class ReconciliationResult(BaseModel):
    run_id: str
    transaction_id: str
    matched: bool
    match_status: str  # MATCHED, FEE_VARIANCE, etc.
    confidence: float  # 0.0 to 1.0
    matched_settlement_id: Optional[str] = None
    matched_bank_transaction_id: Optional[str] = None
    reason_code: str
    score_breakdown: ScoreBreakdown
    evidence: Evidence
    financial_difference_paise: int = 0
    processing_time_ms: float = 0.0
    engine_version: str = "reconciliation-engine-v1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ExceptionItem(BaseModel):
    exception_id: str
    run_id: str
    transaction_id: str
    reason_code: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    priority_score: float
    status: str  # DETECTED, INVESTIGATING, AI_RECOMMENDED, AUTO_RESOLVED, HUMAN_REVIEW, APPROVED, REJECTED, RESOLVED
    financial_impact_paise: int
    confidence: float
    age_days: float = 0.0
    sla_status: str = "WITHIN_SLA"  # WITHIN_SLA, APPROACHING_SLA, BREACHED_SLA
    recommended_action: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    matched_settlement_id: Optional[str] = None
    matched_bank_transaction_id: Optional[str] = None
    evidence: Evidence
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AgentInvestigation(BaseModel):
    investigation_id: str
    exception_id: str
    transaction_id: str
    provider: str  # MOCK, OPENAI, GEMINI
    decision: str  # AUTO_RESOLVE, HUMAN_REVIEW, UNRESOLVED
    confidence: float
    reason_code: str
    summary: str
    evidence_items: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    recommended_action: str
    risk_level: str
    financial_impact_paise: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuditLog(BaseModel):
    audit_id: str
    run_id: Optional[str] = None
    transaction_id: str
    actor_type: str  # SYSTEM, AI_AGENT, HUMAN
    actor_id: str  # engine, agent_mock, user_name
    action: str  # MATCH_DETECTED, EXCEPTION_CREATED, AI_INVESTIGATION, AUTO_RESOLVED, HUMAN_APPROVED, HUMAN_REJECTED, RESOLVED
    previous_state: Optional[str] = None
    new_state: str
    reason: str
    evidence: Dict[str, Any] = {}
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}
