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

    print("\n=== 5) MULTILINGUAL ===")
    en_pw = _run(samples, "en_password")
    en_bill = _run(samples, "en_billing_pii")
    en_pw_status = "LIMIT"
    if en_pw.classification.topic == "password_reset" and en_pw.decision.value == "auto_reply":
        en_pw_status = "ok (unexpectedly strong rules)"
    else:
        limits.append(
            "LIMIT: RU topic rules miss EN access request (locale detected, no true multilingual classify/KB)"
        )
    print(
        f"- en_password: decision={en_pw.decision.value} "
        f"topic={en_pw.classification.topic} locale={en_pw.locale} "
        f"sync_ms={en_pw.latency_ms_sync} => {en_pw_status}"
    )
    en_bill_status = "ok"
    if en_bill.decision.value != "escalate" or not en_bill.classification.pii_suspected:
        en_bill_status = "FAIL"
    if en_bill.locale != "en":
        en_bill_status = "FAIL"
    if en_bill.latency_ms_sync >= SYNC_BUDGET_MS:
        en_bill_status = "FAIL"
    print(
        f"- en_billing_pii: decision={en_bill.decision.value} "
        f"pii={en_bill.classification.pii_suspected} locale={en_bill.locale} "
        f"sync_ms={en_bill.latency_ms_sync} => {en_bill_status}"
    )
    assert en_pw_status in {"LIMIT", "ok (unexpectedly strong rules)"}
    assert en_bill_status == "ok", (
        f"en_billing_pii expected escalate+PII+locale=en, got {en_bill_status}"
    )

    print("\n=== 6) TOXICITY / REJECT_REWRITE ===")
    toxic = _run(samples, "toxic_ru")
    toxic_status = "ok"
    if toxic.decision.value != "reject_rewrite":
        toxic_status = "FAIL"
    if not toxic.classification.toxicity_suspected:
        toxic_status = "FAIL"
    if toxic.draft_status != DraftStatus.READY or not toxic.draft_reply:
        toxic_status = "FAIL"
    if toxic.llm_used:
        toxic_status = "FAIL"
    if toxic.path != "reject_toxic":
        toxic_status = "FAIL"
    if toxic.latency_ms_sync >= SYNC_BUDGET_MS:
        toxic_status = "FAIL"
    # Option B: topic still classified for audit (password_reset expected here)
    print(
        f"- toxic_ru: decision={toxic.decision.value} "
        f"topic={toxic.classification.topic} "
        f"toxicity={toxic.classification.toxicity_suspected} "
        f"llm_used={toxic.llm_used} sync_ms={toxic.latency_ms_sync} => {toxic_status}"
    )
    assert toxic_status == "ok", f"toxic_ru failed: {toxic_status}"

    print("\n=== 7) COMPLEX TEXT ===")
    multi = _run(samples, "multi_intent")
    multi_status = "ok"
    if multi.decision.value != "escalate" or not multi.classification.multi_intent:
        multi_status = "FAIL"
    if multi.latency_ms_sync >= SYNC_BUDGET_MS:
        multi_status = "FAIL"
    print(
        f"- multi_intent: decision={multi.decision.value} "
        f"topic={multi.classification.topic} "
        f"topics_hit={multi.classification.topics_hit} "
        f"multi={multi.classification.multi_intent} "
        f"sync_ms={multi.latency_ms_sync} => {multi_status}"
    )
    assert multi_status == "ok"

    sarcasm = _run(samples, "sarcasm_billing")
    sarcasm_status = "LIMIT"
    sarcasm_note = (
        "LIMIT: sarcasm/indirect money ask may miss billing_payment topic (rules baseline)"
    )
    if (
        sarcasm.classification.topic == "billing_payment"
        and sarcasm.decision.value == "escalate"
    ):
        sarcasm_status = "ok (rules caught billing)"
    elif sarcasm.decision.value == "auto_reply":
        sarcasm_status = "FAIL"
    else:
        limits.append(sarcasm_note)
    if sarcasm.latency_ms_sync >= SYNC_BUDGET_MS:
        sarcasm_status = "FAIL"
    print(
        f"- sarcasm_billing: decision={sarcasm.decision.value} "
        f"topic={sarcasm.classification.topic} "
        f"sync_ms={sarcasm.latency_ms_sync} => {sarcasm_status}"
    )
    assert sarcasm_status in {"LIMIT", "ok (rules caught billing)"}

    mixed = _run(samples, "mixed_locale")
    mixed_status = "ok"
    if mixed.locale != "unknown":
        mixed_status = "FAIL"
    if mixed.decision.value == "auto_reply":
        mixed_status = "FAIL"
    if mixed.latency_ms_sync >= SYNC_BUDGET_MS:
        mixed_status = "FAIL"
    print(
        f"- mixed_locale: decision={mixed.decision.value} "
        f"locale={mixed.locale} topic={mixed.classification.topic} "
        f"sync_ms={mixed.latency_ms_sync} => {mixed_status}"
    )
    assert mixed_status == "ok", f"mixed_locale failed: {mixed_status}"

    print("\n=== 8) BURST / INCIDENT ===")
    burst = _run(samples, "outage_burst")
    burst_status = "ok"
    if burst.path != "burst_incident" or burst.decision.value != "suggest":
        burst_status = "FAIL"
    if burst.llm_used or not burst.draft_reply:
        burst_status = "FAIL"
    if burst.incident_id != "INC-42":
        burst_status = "FAIL"
    if "INC-42" not in (burst.draft_reply or ""):
        burst_status = "FAIL"
    if burst.latency_ms_sync >= SYNC_BUDGET_MS:
        burst_status = "FAIL"
    print(
        f"- outage_burst: decision={burst.decision.value} path={burst.path} "
        f"incident_id={burst.incident_id} llm_used={burst.llm_used} "
        f"sync_ms={burst.latency_ms_sync} => {burst_status}"
    )
    assert burst_status == "ok", f"outage_burst failed: {burst_status}"

    print("\nOK: smoke passed (with known limits)" if limits else "\nOK: smoke passed")
    for note in limits:
        print(f"  noted: {note}")


if __name__ == "__main__":
    main()
