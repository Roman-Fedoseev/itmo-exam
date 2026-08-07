"""Sync hot path (<500ms): locale + toxicity + classify + retrieve + policy.
Draft path is separate (async in production; sequential in PoC but not in sync budget).
"""

from __future__ import annotations

import time
import uuid

from app.classifier import classify
from app.llm import LLMUnavailableError, burst_incident_template, generate_draft, template_draft
from app.locale import resolve_locale
from app.models import Decision, DraftStatus, ProcessResult, RiskLevel, TicketIn
from app.retrieval import retrieve
from app.toxicity import rewrite_template, toxicity_hit

AUTO_TOPICS = {"password_reset", "faq_general"}
CONFIDENCE_AUTO = 0.7
CONFIDENCE_SUGGEST = 0.45


def decide(classification, hits, locale: str = "ru") -> tuple[Decision, str, str]:
    if classification.multi_intent:
        return (
            Decision.ESCALATE,
            "multi-intent ticket - max(risk), no auto (operator merges threads)",
            "fallback_risky",
        )
    if locale == "unknown":
        return (
            Decision.ESCALATE,
            "unknown/mixed locale - safer to escalate than auto in wrong language",
            "fallback_risky",
        )
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


def _build_draft(
    ticket: TicketIn,
    classification,
    hits,
    decision: Decision,
    locale: str,
    *,
    burst: bool = False,
):
    """Draft path: not part of sync latency budget."""
    if decision == Decision.ESCALATE:
        return None, DraftStatus.SKIPPED, False, 0.0
    if decision == Decision.REJECT_REWRITE:
        return rewrite_template(locale), DraftStatus.READY, False, 0.0
    if burst and ticket.incident_id:
        return (
            burst_incident_template(ticket.incident_id, hits),
            DraftStatus.READY,
            False,
            0.0,
        )

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
    locale = resolve_locale(ticket.locale, text)
    toxic = toxicity_hit(text)
    # Option B: always classify/retrieve for audit; toxicity overrides decision
    classification = classify(text)
    if toxic:
        classification = classification.model_copy(update={"toxicity_suspected": True})
    hits = retrieve(text, classification.topic)

    burst = bool(
        ticket.incident_id
        and classification.topic == "service_outage"
        and not toxic
    )

    if toxic:
        decision = Decision.REJECT_REWRITE
        reason = (
            "toxicity/abuse detected - ask user to rewrite; "
            "not escalated to operator queue"
        )
        path = "reject_toxic"
    elif burst:
        # Тикет привязан к инциденту → status template, не LLM на каждый дубликат
        decision = Decision.SUGGEST
        reason = (
            f"incident {ticket.incident_id} burst/dedup - status template, LLM skipped"
        )
        path = "burst_incident"
    else:
        decision, reason, path = decide(classification, hits, locale)
    latency_sync = (time.perf_counter() - t0) * 1000

    # --- DRAFT PATH (async in prod; measured separately) ---
    draft, draft_status, llm_used, latency_draft = _build_draft(
        ticket, classification, hits, decision, locale, burst=burst
    )

    if draft_status == DraftStatus.DEGRADED:
        path = "degraded_no_llm"
        reason = f"{reason}; LLM down -> template fallback"
        if decision == Decision.AUTO_REPLY:
            decision = Decision.SUGGEST
            reason += "; auto_reply downgraded to suggest"

    return ProcessResult(
        ticket_id=ticket.ticket_id,
        locale=locale,
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
        incident_id=ticket.incident_id,
        log_id=str(uuid.uuid4()),
    )
