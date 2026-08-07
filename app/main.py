"""PoC API: demos for happy / risky / degrade / fixtures list."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.models import ProcessResult, TicketIn
from app.pipeline import process_ticket

app = FastAPI(title="Support Ticket PoC", version="0.2.0")

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sample_tickets.json"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _load() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _append_log(result: ProcessResult) -> None:
    with (LOG_DIR / "decisions.jsonl").open("a", encoding="utf-8") as f:
        f.write(result.model_dump_json() + "\n")


def _run_named(name: str, **overrides) -> ProcessResult:
    tickets = _load()
    if name not in tickets:
        raise HTTPException(status_code=404, detail=f"unknown fixture: {name}")
    payload = dict(tickets[name])
    payload.update(overrides)
    result = process_ticket(TicketIn(**payload))
    _append_log(result)
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demo/fixtures")
def list_fixtures():
    return sorted(_load().keys())


@app.post("/tickets/process", response_model=ProcessResult)
def process(ticket: TicketIn) -> ProcessResult:
    result = process_ticket(ticket)
    _append_log(result)
    return result


@app.post("/demo/happy", response_model=ProcessResult)
def demo_happy() -> ProcessResult:
    return _run_named("happy")


@app.post("/demo/risky", response_model=ProcessResult)
def demo_risky() -> ProcessResult:
    return _run_named("risky")


@app.post("/demo/llm-down", response_model=ProcessResult)
def demo_llm_down() -> ProcessResult:
    return _run_named("happy", force_llm_down=True)


@app.post("/demo/outage", response_model=ProcessResult)
def demo_outage() -> ProcessResult:
    return _run_named("outage")
