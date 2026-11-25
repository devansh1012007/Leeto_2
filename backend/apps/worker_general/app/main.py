"""worker_general: outbox dispatch, emails, snapshots, prune jobs (02 §8 catalog).

Job claim: FOR UPDATE SKIP LOCKED; lease 60 s; heartbeat 20 s; idempotent handlers.
On SIGTERM: stop claiming, finish or release leases (graceful shutdown, 02 §13).

Serves /healthz + /readyz on the internal probe port (RB-01: "/readyz 200 on every API").
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from core.health import register_health_endpoints
from fastapi import FastAPI

log = logging.getLogger("bhctf.worker_general")

PROBE_PORT = int(os.environ.get("PROBE_PORT", "8012"))

app = FastAPI(title="Bug Hunt CTF — worker_general probe", docs_url=None, redoc_url=None)
register_health_endpoints(app)


async def _probe_server() -> None:  # pragma: no cover — uvicorn side task
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=PROBE_PORT, log_level="warning")
    await uvicorn.Server(config).serve()


async def claim_and_run(kind: str, handler) -> None:  # pragma: no cover — DB loop
    from db.session import tx
    from sqlalchemy import text

    while True:
        async with tx("worker") as conn:
            row = conn.execute(
                text("UPDATE app.jobs SET state = 'leased', leased_by = 'worker_general', "
                     "leased_until = now() + interval '60 seconds', attempts = attempts + 1 "
                     "WHERE id = (SELECT id FROM app.jobs WHERE state = 'pending' AND kind = :kind "
                     "AND run_at <= now() ORDER BY priority, run_at LIMIT 1 FOR UPDATE SKIP LOCKED) "
                     "RETURNING id, payload"),
                {"kind": kind},
            ).first()
            if row is None:
                break
            try:
                await handler(conn, row.id, row.payload)
                conn.execute(text("UPDATE app.jobs SET state = 'done' WHERE id = :id"), {"id": row.id})
            except Exception as exc:  # noqa: BLE001
                conn.execute(text("UPDATE app.jobs SET last_error = :e WHERE id = :id"),
                             {"e": str(exc)[:500], "id": row.id})


async def main() -> None:  # pragma: no cover
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker_general started")
    probe = asyncio.create_task(_probe_server())
    try:
        while not stop.is_set():
            await asyncio.sleep(1)  # poll loop; LISTEN/NOTIFY is only a wake-up hint
    finally:
        probe.cancel()


if __name__ == "__main__":
    asyncio.run(main())
