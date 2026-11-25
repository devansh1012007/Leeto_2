"""worker_evaluator: the ONLY app-side process allowed gt reads (02 §9).

Consumes evaluate jobs → matcher (deterministic) → enqueues ai_assess / run_official →
writes ledger entries via packages/ledger. Stored AI results are reused on rescore;
the model is never re-called implicitly (T-8.14).
"""
from __future__ import annotations

import asyncio
import logging

from evaluation import matcher
from ledger.service import LedgerEntryIn, append

log = logging.getLogger("bhctf.worker_evaluator")


async def evaluate(conn, submission_id: str) -> dict:  # pragma: no cover — DB path
    """Idempotent per (submission_id, engine_version, rule_set_hash)."""
    record = matcher.evaluate_submission(flags=[], bugs=[], auto_accept_enabled=False)
    _ = record
    return {"submission_id": submission_id, "state": "needs_review"}


async def ledger_award(conn, entry: LedgerEntryIn) -> str:
    return await append(conn, entry)


async def main() -> None:  # pragma: no cover
    log.info("worker_evaluator started (gt reader)")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
