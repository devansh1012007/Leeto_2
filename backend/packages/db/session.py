"""Async DB engine/session + transaction helper with the B6 lock-order discipline."""
from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_ENGINES: dict[str, AsyncEngine] = {}


def engine_for(role: str = "app") -> AsyncEngine:
    """One pooled engine per DB role (app_api / admin_api / evaluator / ...)."""
    if role in _ENGINES:
        return _ENGINES[role]
    s = get_settings()
    user = {"app": s.pg_user, "admin": s.pg_user, "evaluator": s.pg_user}.get(role, s.pg_user)
    eng = create_async_engine(s.dsn(user=user), pool_size=8, max_overflow=8, pool_pre_ping=True)
    _ENGINES[role] = eng
    return eng


@asynccontextmanager
async def tx(role: str = "app") -> AsyncIterator[AsyncConnection]:
    """One short READ COMMITTED transaction (B6 Phase 2).

    Lock order inside the caller's service code MUST be:
      idempotency → stage state → clock_timestamp() once → team/participant → quota → writes.
    """
    async with engine_for(role).connect() as conn:
        async with conn.begin():
            yield conn


@asynccontextmanager
async def read_only(role: str = "app", *, statement_timeout_ms: int = 800) -> AsyncIterator[AsyncConnection]:
    """Read path: NO transaction, short statement timeout (B6)."""
    async with engine_for(role).connect() as conn:
        await conn.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": statement_timeout_ms})
        yield conn


async def clock_now(conn: AsyncConnection) -> Any:
    """Authoritative time: clock_timestamp() — call ONCE after the stage-state lock (B6/ADR-012)."""
    row = await conn.execute(text("SELECT clock_timestamp() AS now"))
    return row.scalar_one()


def new_idempotency_key() -> str:
    return f"idem_{secrets.token_urlsafe(24)}"


def payload_hash(body: Any) -> str:
    import json

    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
