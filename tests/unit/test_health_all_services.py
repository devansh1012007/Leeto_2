"""Every service exposes /healthz (always 200) and /readyz (fail-closed 503 without DB).

RB-01 requires "/readyz 200 on every API". This test covers all six services:
api_participant, api_admin, runner_gateway, scheduler, worker_evaluator, worker_general.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helpers import load_app

SERVICES = [
    "api_participant",
    "api_admin",
    "runner_gateway",
    "scheduler",
    "worker_evaluator",
    "worker_general",
]


@pytest.fixture()
def clients(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
    out = {}
    for name in SERVICES:
        app = load_app(name).app
        out[name] = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return out


@pytest.mark.parametrize("service", SERVICES)
async def test_healthz_ok(clients, service):
    r = await clients[service].get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize("service", SERVICES)
async def test_readyz_fail_closed_without_db(clients, service):
    r = await clients[service].get("/readyz")
    # no Postgres in this environment: must fail closed (503), never a lying 200
    assert r.status_code == 503
    assert "db_unreachable" in r.json()["detail"]["problems"]
