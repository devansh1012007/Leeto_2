"""Shared /healthz + /readyz registration for every service (RB-01: "/readyz 200 on every API").

- /healthz: liveness, no dependencies — 200 always.
- /readyz: readiness, fail-closed 503 when the DB is unreachable (R-17/B12);
  never a lying 200.
"""
from __future__ import annotations

from db.session import tx
from fastapi import FastAPI, HTTPException
from sqlalchemy import text


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
