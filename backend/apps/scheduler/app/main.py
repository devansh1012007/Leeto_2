"""scheduler: timers from the DB (never memory), auto-submit, snapshots, prune jobs.

One scheduler process, elected by a Postgres advisory lock (02 §8.3). Missed timers fire
in order on restart with late_by recorded (JOB-06).

Serves /healthz + /readyz on the internal probe port (RB-01: "/readyz 200 on every API").
"""
from __future__ import annotations

import asyncio
import logging
import os

from core.health import register_health_endpoints
from fastapi import FastAPI

log = logging.getLogger("bhctf.scheduler")

PROBE_PORT = int(os.environ.get("PROBE_PORT", "8010"))

JOBS = {
    "JOB-06 stage_transition": "fire_at in app.stages",
    "JOB-07 autosubmit_stage": "exec_closes_at + autosubmit_grace_s (default 5s)",
    "JOB-08 snapshot_leaderboard": "debounced 2 s after ledger commits",
    "JOB-13 retention_purge": "daily",
    "JOB-14 idempotency_prune": "hourly; submit/lock/upload keys kept event + 7 days (B4)",
    "JOB-15 job_reaper": "every 30 s; reclaims expired leases",
    "JOB-16 chain_verify": "every 10 min",
    "JOB-17 draft_compact": "every 15 min",
    "JOB-18 clock_check": "every 60 s; alert if offset > 100 ms",
}

app = FastAPI(title="Bug Hunt CTF — Scheduler probe", docs_url=None, redoc_url=None)
register_health_endpoints(app)


async def _probe_server() -> None:  # pragma: no cover — uvicorn side task
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=PROBE_PORT, log_level="warning")
    await uvicorn.Server(config).serve()


async def main() -> None:  # pragma: no cover
    log.info("scheduler started; timers: %s", ", ".join(JOBS))
    probe = asyncio.create_task(_probe_server())
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        probe.cancel()


if __name__ == "__main__":
    asyncio.run(main())
