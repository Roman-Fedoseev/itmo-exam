"""Определение языка тикета (PoC-эвристика).

В проде: явный locale от канала + нормальный lang-detect;
classify/retrieve/draft опираются на locale, policy — нет.
"""

from __future__ import annotations

from typing import Optional


def detect_locale(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    cyr = sum(1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё")
    lat = sum(1 for c in letters if "a" <= c.lower() <= "z")
    # Смесь RU+EN в заметной доле → unknown (не угадываем auto-язык)
    if cyr > 0 and lat > 0:
        minority_ratio = min(cyr, lat) / max(cyr, lat)
        if minority_ratio >= 0.35:
            return "unknown"
    if cyr >= lat and cyr > 0:
        return "ru"
    if lat > cyr and lat > 0:
        return "en"
    return "unknown"


def resolve_locale(explicit: Optional[str], text: str) -> str:
    if explicit:
        return explicit.lower().strip()
    return detect_locale(text)
