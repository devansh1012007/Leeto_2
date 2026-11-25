"""Shared /healthz + /readyz + /metrics registration for every service (RB-01: "/readyz
200 on every API"; /metrics is internal-network only, never Tunnel-routed).

- /healthz: liveness, no dependencies — 200 always.
- /readyz: readiness, fail-closed 503 when the DB is unreachable (R-17/B12);
  never a lying 200.
- /metrics: Prometheus text format; process counters only, no user data.
"""
from __future__ import annotations

import os
import time

from db.session import tx
from fastapi import FastAPI, HTTPException, Response
from sqlalchemy import text

_STARTED_AT = time.time()


def _prom_metrics() -> str:
    """Minimal Prometheus text exposition (process uptime + build info)."""
    uptime = time.time() - _STARTED_AT
    env = os.environ.get("ENV", "dev")
    lines = [
        "# HELP bhctf_up Service liveness (1 = up).",
        "# TYPE bhctf_up gauge",
        "bhctf_up 1",
        "# HELP bhctf_uptime_seconds Process uptime in seconds.",
        "# TYPE bhctf_uptime_seconds counter",
        f"bhctf_uptime_seconds {uptime:.1f}",
        "# HELP bhctf_build_info Build metadata.",
        "# TYPE bhctf_build_info gauge",
        f'bhctf_build_info{{env="{env}",service="api"}} 1',
    ]
    return "\n".join(lines) + "\n"


def register_health_endpoints(app: FastAPI) -> None:
    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict:
        problems: list[str] = []
        try:
            async with tx() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 — fail closed on any DB failure
            problems.append("db_unreachable")
        if problems:
            raise HTTPException(status_code=503, detail={"problems": problems})
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=_prom_metrics(), media_type="text/plain; version=0.0.4")
