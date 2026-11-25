"""/readyz fails closed when the DB is unreachable (R-17/B12)."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helpers import load_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
    app = load_app("api_participant").app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_healthz_ok_without_db(client):
    r = await client.get("/healthz")
    assert r.status_code == 200


async def test_readyz_reports_problems_when_db_down(client):
    r = await client.get("/readyz")
    # no Postgres in this environment: must fail closed (503), never a lying 200
    assert r.status_code == 503
