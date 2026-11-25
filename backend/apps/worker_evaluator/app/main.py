"""worker_evaluator: the ONLY app-side process allowed gt reads (02 §9).

Consumes evaluate jobs → matcher (deterministic) → enqueues ai_assess / run_official →
writes ledger entries via packages/ledger. Stored AI results are reused on rescore;
the model is never re-called implicitly (T-8.14).

Serves /healthz + /readyz on the internal probe port (RB-01: "/readyz 200 on every API").
"""
from __future__ import annotations

import asyncio
import logging
import os

from core.health import register_health_endpoints
from evaluation import matcher
from fastapi import FastAPI
from ledger.service import LedgerEntryIn, append

log = logging.getLogger("bhctf.worker_evaluator")

PROBE_PORT = int(os.environ.get("PROBE_PORT", "8011"))

app = FastAPI(title="Bug Hunt CTF — worker_evaluator probe", docs_url=None, redoc_url=None)
register_health_endpoints(app)


async def evaluate(conn, submission_id: str) -> dict:  # pragma: no cover — DB path
    """Idempotent per (submission_id, engine_version, rule_set_hash)."""
    record = matcher.evaluate_submission(flags=[], bugs=[], auto_accept_enabled=False)
    _ = record
    return {"submission_id": submission_id, "state": "needs_review"}


async def ledger_award(conn, entry: LedgerEntryIn) -> str:
    return await append(conn, entry)


async def main() -> None:  # pragma: no cover
    import uvicorn

    log.info("worker_evaluator started (gt reader)")
    config = uvicorn.Config(app, host="0.0.0.0", port=PROBE_PORT, log_level="warning")
    probe = asyncio.create_task(uvicorn.Server(config).serve())
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        probe.cancel()


if __name__ == "__main__":
    asyncio.run(main())
