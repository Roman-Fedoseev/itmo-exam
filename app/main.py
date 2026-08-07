"""MVP API: process ticket + two demos."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from app.models import ProcessResult, TicketIn
from app.pipeline import process_ticket

app = FastAPI(title="Support Ticket PoC", version="0.1.0")

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sample_tickets.json"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _append_log(result: ProcessResult) -> None:
    with (LOG_DIR / "decisions.jsonl").open("a", encoding="utf-8") as f:
        f.write(result.model_dump_json() + "\n")


def _demo(name: str) -> ProcessResult:
    tickets = json.loads(FIXTURES.read_text(encoding="utf-8"))
    result = process_ticket(TicketIn(**tickets[name]))
    _append_log(result)
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets/process", response_model=ProcessResult)
def process(ticket: TicketIn) -> ProcessResult:
    result = process_ticket(ticket)
    _append_log(result)
    return result


@app.post("/demo/happy", response_model=ProcessResult)
def demo_happy() -> ProcessResult:
    return _demo("happy")


@app.post("/demo/risky", response_model=ProcessResult)
def demo_risky() -> ProcessResult:
    return _demo("risky")
