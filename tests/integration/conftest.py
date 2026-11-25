"""Integration tests need a real Postgres (CI service or local docker).
Skipped automatically when PG is unreachable so the unit CI stays green."""
from __future__ import annotations

import pytest


def _pg_available() -> bool:
    try:
        import psycopg
        from core.config import get_settings

        s = get_settings()
        with psycopg.connect(s.dsn().replace("+psycopg", ""), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Postgres not reachable (integration tests run in CI)")


@pytest.fixture()
def db_conn():
    import psycopg
    from core.config import get_settings

    s = get_settings()
    conn = psycopg.connect(s.dsn().replace("+psycopg", ""), autocommit=True)
    yield conn
    conn.close()
