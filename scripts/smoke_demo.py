"""MVP smoke: happy path + risky escalate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import DraftStatus, TicketIn  # noqa: E402
from app.pipeline import process_ticket  # noqa: E402


def main() -> None:
    samples = json.loads((ROOT / "fixtures" / "sample_tickets.json").read_text(encoding="utf-8"))

    print("=== HAPPY ===")
    happy = process_ticket(TicketIn(**samples["happy"]))
    print(happy.model_dump_json(indent=2))

    print("\n=== RISKY ===")
    risky = process_ticket(TicketIn(**samples["risky"]))
    print(risky.model_dump_json(indent=2))

    assert happy.decision.value in {"auto_reply", "suggest"}
    assert happy.draft_status == DraftStatus.READY
    assert happy.latency_ms_sync < 500
    assert risky.decision.value == "escalate"
    assert risky.draft_status == DraftStatus.SKIPPED
    print("\nOK: MVP smoke passed")


if __name__ == "__main__":
    main()
