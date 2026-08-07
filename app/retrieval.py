"""Простой retrieval по keyword overlap (заглушка вместо embeddings/vector DB)."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import RetrievalHit

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "knowledge_base.json"


def _load_kb() -> list[dict]:
    with FIXTURES.open(encoding="utf-8") as f:
        return json.load(f)


def retrieve(query: str, topic: str, top_k: int = 2) -> list[RetrievalHit]:
    kb = _load_kb()
    q = query.lower()
    ranked: list[RetrievalHit] = []

    for item in kb:
        text = f"{item['title']} {item['body']} {' '.join(item.get('tags', []))}".lower()
        overlap = sum(1 for token in q.split() if len(token) > 3 and token in text)
        topic_bonus = 2 if topic in item.get("tags", []) else 0
        score = overlap + topic_bonus
        if score <= 0:
            continue
        ranked.append(
            RetrievalHit(
                source=item["id"],
                title=item["title"],
                snippet=item["body"][:220],
                score=float(score),
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:top_k]
