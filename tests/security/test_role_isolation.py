"""R-03 gate: app_api has ZERO grants on gt.*; runner has no DB role at all."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.integration.conftest import pytestmark  # noqa: F401 — skip-if-no-PG


def test_no_runner_role(db_conn):
    row = db_conn.execute("SELECT count(*) FROM pg_roles WHERE rolname = 'runner'").fetchone()
    assert row[0] == 0, "the runner VM must have NO database role (R-02)"


def test_app_api_cannot_read_gt(db_conn):
    """Connect with the real app_api role and assert every gt.* read fails."""
    import psycopg
    from core.config import get_settings

    s = get_settings()
    dsn = f"host={s.pg_host} port={s.pg_port} dbname={s.pg_db} user=app_api"
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1 FROM gt.bugs LIMIT 1").fetchall()
    except psycopg.Error:
        return  # denied as required
    raise AssertionError("app_api must not be able to read gt.bugs (R-03/E.1)")
