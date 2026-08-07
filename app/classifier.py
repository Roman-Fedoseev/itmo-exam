"""Быстрый sync-классификатор: правила + простой scoring.

В проде: lightweight model / embeddings classifier (<500ms).
LLM здесь намеренно НЕ используется — дорого и медленно для hot path.
"""

from __future__ import annotations

import re

from app.models import Classification, RiskLevel

TOPIC_RULES: dict[str, list[str]] = {
    "password_reset": ["пароль", "сброс", "войти", "логин", "password", "reset", "код из смс"],
    "billing_payment": ["оплат", "списан", "карт", "платеж", "refund", "возврат", "деньги"],
    "service_outage": ["не работает", "лежит", "авария", "ошибка 5", "downtime", "недоступ", "503"],
    "account_delete": ["удалить аккаунт", "удаление аккаунта", "закрыть аккаунт"],
    "abuse_legal": ["юрист", "роспотреб", "прокуратур", "исков", "жалоба в"],
    "faq_general": ["как", "где найти", "инструкц", "faq", "профиль", "настройк"],
}

HIGH_RISK_TOPICS = {"billing_payment", "account_delete", "abuse_legal"}
PII_PATTERNS = [
    re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]
INJECTION_HINTS = [
    "игнорируй инструкции",
    "забудь правила",
    "ignore previous",
    "ignore all instructions",
    "системный промпт",
    "ты теперь",
]


def classify(text: str) -> Classification:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for topic, kws in TOPIC_RULES.items():
        scores[topic] = sum(1 for kw in kws if kw in lowered)

    best_topic = max(scores, key=scores.get)
    hits = scores[best_topic]
    confidence = min(0.95, 0.35 + 0.2 * hits) if hits else 0.25
    if hits == 0:
        best_topic = "unknown"

    pii = any(p.search(text) for p in PII_PATTERNS)
    injection = any(h in lowered for h in INJECTION_HINTS)

    if injection or pii or best_topic in HIGH_RISK_TOPICS:
        risk = RiskLevel.HIGH
    elif best_topic == "service_outage":
        risk = RiskLevel.MEDIUM
    elif best_topic in {"password_reset", "faq_general"} and confidence >= 0.55:
        risk = RiskLevel.LOW
    else:
        risk = RiskLevel.MEDIUM

    if pii or injection:
        confidence = min(confidence, 0.5)

    return Classification(
        topic=best_topic,
        risk=risk,
        confidence=round(confidence, 3),
        method="rules",
        pii_suspected=pii,
        injection_suspected=injection,
    )
