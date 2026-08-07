"""Toxicity / abuse gate on sync path.

PoC: hard word list (tiny, demo-only — not a full lexicon).
Target: list first (short-circuit) → tiny toxicity model (distil/BERT-class)
still inside p95 <500ms budget; LLM not used here.

Hit → reject_rewrite + template to user (not escalate to operator queue).
"""

from __future__ import annotations

# Учебный список маркеров (не полный словарь). Достаточно для smoke.
TOXIC_MARKERS = [
    "идиот",
    "идиоты",
    "урод",
    "уроды",
    "дебил",
    "дебилы",
    "мудак",
    "мудаки",
    "сука",
    "блять",
    "блядь",
    "пидор",
    "хуй",
    "нахуй",
    "fuck you",
    "fucking idiots",
    "stupid assholes",
]

REWRITE_TEMPLATE_RU = (
    "Пожалуйста, переформулируйте обращение без оскорблений и нецензурной лексики — "
    "тогда сможем помочь."
)


def toxicity_hit(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in TOXIC_MARKERS)


def rewrite_template(locale: str = "ru") -> str:
    # PoC: один RU-шаблон; target — per locale
    _ = locale
    return REWRITE_TEMPLATE_RU
