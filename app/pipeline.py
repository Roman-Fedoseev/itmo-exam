"""Sync hot path (<500ms): classify + retrieve + policy.
Draft path is separate (async in production; sequential in PoC but not in sync budget).
"""

from __future__ import annotations

import time
import uuid

from app.classifier import classify
from app.llm import LLMUnavailableError, generate_draft, template_draft
from app.models import Decision, DraftStatus, ProcessResult, RiskLevel, TicketIn
from app.retrieval import retrieve

AUTO_TOPICS = {"password_reset", "faq_general"}
CONFIDENCE_AUTO = 0.7
CONFIDENCE_SUGGEST = 0.45


def decide(classification, hits) -> tuple[Decision, str, str]:
    if (
        classification.pii_suspected
        or classification.injection_suspected
        or classification.risk == RiskLevel.HIGH
    ):
        why = "high risk / PII / injection - auto-reply forbidden, needs operator"
        return Decision.ESCALATE, why, "fallback_risky"
    if classification.confidence < CONFIDENCE_SUGGEST or classification.topic == "unknown":
        return (
            Decision.ESCALATE,
            "low confidence - safer to escalate to human",
            "fallback_risky",
        )
    if (
        classification.topic in AUTO_TOPICS
        and classification.risk == RiskLevel.LOW
        and classification.confidence >= CONFIDENCE_AUTO
        and hits
    ):
        return (
            Decision.AUTO_REPLY,
            "safe topic + high confidence + KB hit",
            "happy",
        )
    return (
        Decision.SUGGEST,
        "draft for operator (suggest-mode)",
        "happy",
    )


def _build_draft(ticket: TicketIn, classification, hits, decision: Decision):
    """Draft path: not part of sync latency budget."""
    if decision == Decision.ESCALATE:
        return None, DraftStatus.SKIPPED, False, 0.0

    t0 = time.perf_counter()
    llm_used = False
    status = DraftStatus.READY
    try:
        draft = generate_draft(
            ticket.body,
            classification,
            hits,
            force_down=ticket.force_llm_down,
        )
        llm_used = True
    except LLMUnavailableError:
        draft = template_draft(hits, classification.topic)
        status = DraftStatus.DEGRADED
    latency = (time.perf_counter() - t0) * 1000
    return draft, status, llm_used, round(latency, 2)


def process_ticket(ticket: TicketIn) -> ProcessResult:
    # --- SYNC PATH (contract: <500ms) ---
    t0 = time.perf_counter()
    text = f"{ticket.subject}\n{ticket.body}".strip()
    classification = classify(text)
    hits = retrieve(text, classification.topic)
    decision, reason, path = decide(classification, hits)
    latency_sync = (time.perf_counter() - t0) * 1000

    # --- DRAFT PATH (async in prod; measured separately) ---
    draft, draft_status, llm_used, latency_draft = _build_draft(
        ticket, classification, hits, decision
    )

    if draft_status == DraftStatus.DEGRADED:
        path = "degraded_no_llm"
        reason = f"{reason}; LLM down -> template fallback"
        if decision == Decision.AUTO_REPLY:
            decision = Decision.SUGGEST
            reason += "; auto_reply downgraded to suggest"

    return ProcessResult(
        ticket_id=ticket.ticket_id,
        classification=classification,
        retrieval=hits,
        decision=decision,
        reason=reason,
        path=path,
        latency_ms_sync=round(latency_sync, 2),
        latency_ms_draft=latency_draft,
        draft_status=draft_status,
        draft_reply=draft,
        llm_used=llm_used,
        log_id=str(uuid.uuid4()),
    )
