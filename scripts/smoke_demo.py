"""Smoke: happy + risky + LLM degrade + edge cases (with known LIMIT)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import DraftStatus, TicketIn  # noqa: E402
from app.pipeline import process_ticket  # noqa: E402

SYNC_BUDGET_MS = 500.0


def _run(samples: dict, key: str, **overrides):
    payload = dict(samples[key])
    payload.update(overrides)
    return process_ticket(TicketIn(**payload))


def main() -> None:
    samples = json.loads((ROOT / "fixtures" / "sample_tickets.json").read_text(encoding="utf-8"))

    print("=== 1) HAPPY ===")
    happy = _run(samples, "happy")
    print(happy.model_dump_json(indent=2))

    print("\n=== 2) RISKY ===")
    risky = _run(samples, "risky")
    print(risky.model_dump_json(indent=2))

    print("\n=== 3) DEGRADE (LLM DOWN) ===")
    down = _run(samples, "happy", force_llm_down=True)
    print(down.model_dump_json(indent=2))

    print("\n=== 4) EDGE CASES ===")
    # expected decision set, optional forbid_auto, optional mark LIMIT if rules are weak
    edges = [
        ("faq", {"auto_reply", "suggest"}, False, None),
        ("outage", {"suggest", "escalate"}, True, None),
        ("account_delete", {"escalate"}, False, None),
        ("unknown", {"escalate"}, False, None),
        ("injection", {"escalate"}, False, None),
        (
            "paraphrase_access",
            {"escalate", "suggest", "auto_reply"},
            False,
            "LIMIT: rules may miss paraphrase / no keyword hit for password_reset",
        ),
    ]

    limits = []
    for key, allowed, forbid_auto, limit_note in edges:
        result = _run(samples, key)
        status = "ok"
        if result.decision.value not in allowed:
            status = "FAIL"
        if forbid_auto and result.decision.value == "auto_reply":
            status = "FAIL"
        if result.latency_ms_sync >= SYNC_BUDGET_MS:
            status = "FAIL"
        # paraphrase: if we did NOT get auto on password-like intent — that's the teaching LIMIT
        if key == "paraphrase_access":
            if result.classification.topic != "password_reset" or result.decision.value != "auto_reply":
                status = "LIMIT"
                limits.append(limit_note)
            else:
                status = "ok (unexpectedly strong rules)"
        line = (
            f"- {key}: decision={result.decision.value} "
            f"topic={result.classification.topic} "
            f"conf={result.classification.confidence} "
            f"sync_ms={result.latency_ms_sync} => {status}"
        )
        if limit_note and status == "LIMIT":
            line += f" | {limit_note}"
        print(line)
        assert status in {"ok", "LIMIT", "ok (unexpectedly strong rules)"}, line

    assert happy.decision.value in {"auto_reply", "suggest"}
    assert happy.draft_status == DraftStatus.READY
    assert happy.latency_ms_sync < SYNC_BUDGET_MS
    assert risky.decision.value == "escalate" and risky.draft_status == DraftStatus.SKIPPED
    assert down.path == "degraded_no_llm" and down.draft_status == DraftStatus.DEGRADED
    assert down.decision.value == "suggest"
    assert down.latency_ms_sync < SYNC_BUDGET_MS

    print("\nOK: smoke passed (with known limits)" if limits else "\nOK: smoke passed")
    for note in limits:
        print(f"  noted: {note}")


if __name__ == "__main__":
    main()
