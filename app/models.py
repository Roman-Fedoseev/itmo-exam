from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Decision(str, Enum):
    AUTO_REPLY = "auto_reply"  # только safe + high confidence
    SUGGEST = "suggest"  # черновик оператору
    ESCALATE = "escalate"  # человек, без авто-закрытия


class DraftStatus(str, Enum):
    SKIPPED = "skipped"  # escalate — draft не нужен
    READY = "ready"  # mock/LLM draft готов
    DEGRADED = "degraded"  # LLM down → template
    # в проде был бы ещё pending (очередь); в PoC draft строится сразу после sync


class TicketIn(BaseModel):
    ticket_id: str
    channel: str = Field(description="chat | email | web | mobile")
    subject: str = ""
    body: str
    # PoC-флаг: симулировать недоступность LLM на draft-пути
    force_llm_down: bool = False


class Classification(BaseModel):
    topic: str
    risk: RiskLevel
    confidence: float
    method: str  # rules | mock_ml
    pii_suspected: bool = False
    injection_suspected: bool = False


class RetrievalHit(BaseModel):
    source: str
    title: str
    snippet: str
    score: float


class ProcessResult(BaseModel):
    ticket_id: str
    classification: Classification
    retrieval: list[RetrievalHit]
    decision: Decision
    reason: str
    path: str  # happy | fallback_risky | degraded_no_llm
    # sync budget: classify + retrieve + policy ONLY (<500ms contract)
    latency_ms_sync: float
    # draft path measured separately (async in production)
    latency_ms_draft: float
    draft_status: DraftStatus
    draft_reply: Optional[str]
    llm_used: bool
    log_id: str
