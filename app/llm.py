"""Мок LLM + режим деградации.

В PoC нет внешнего API: generate() либо возвращает черновик, либо падает.
При падении пайплайн использует шаблон из KB (degraded path).
"""

from __future__ import annotations

from app.models import Classification, RetrievalHit


class LLMUnavailableError(RuntimeError):
    pass


def generate_draft(
    ticket_body: str,
    classification: Classification,
    hits: list[RetrievalHit],
    *,
    force_down: bool = False,
) -> str:
    if force_down:
        raise LLMUnavailableError("LLM API unavailable (simulated)")

    context = hits[0].snippet if hits else "нет релевантного фрагмента KB"
    return (
        f"[draft LLM] Тема: {classification.topic}.\n"
        f"Кратко по сути обращения: {ticket_body[:160]}...\n"
        f"Опора на KB: {context}\n"
        "If the issue remains, reply in this ticket."
    )


def template_draft(hits: list[RetrievalHit], topic: str) -> str:
    if hits:
        return (
            f"[degraded template] Topic '{topic}':\n"
            f"{hits[0].title}\n{hits[0].snippet}\n"
            "Answer built without LLM (fallback)."
        )
    return (
        f"[degraded template] No template for topic '{topic}'. "
        "Ticket routed to operator."
    )


def burst_incident_template(incident_id: str, hits: list[RetrievalHit]) -> str:
    """Массовый инцидент: один status-текст на тысячи тикетов, без LLM."""
    status_url = "https://status.example"
    kb_hint = hits[0].snippet if hits else "Мы уже разбираем массовый сбой."
    return (
        f"[incident status template] Инцидент {incident_id}.\n"
        f"{kb_hint}\n"
        f"Актуальный статус: {status_url}\n"
        "Ответ без LLM (burst/dedup mode). Если проблема останется после восстановления — напишите снова."
    )
