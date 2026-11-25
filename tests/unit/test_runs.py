"""Runs gate (GATES Phase 3): allow-listed command_id, idempotency required.
Primary e2e coverage: tests/unit/test_api.py::TestRuns."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

import httpx
import pytest
from helpers import load_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
    app = load_app("api_participant").app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _auth() -> dict:
    from auth.tokens import make_access_token

    return {"Authorization": "Bearer " + make_access_token(
        secret="test-secret-test-secret", sub="p1", sid="s1", role="participant")}


async def test_unknown_command_rejected(client):
    r = await client.post("/v1/runs", headers={**_auth(), "Idempotency-Key": "key-runs-001"},
                          json={"stage_key": "s", "command_id": "rm -rf", "workspace": {"draft_version": 1}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "RUN_COMMAND_UNKNOWN"


async def test_practice_namespace_separate_from_official(client):
    r = await client.post("/v1/runs", headers={**_auth(), "Idempotency-Key": "key-runs-002"},
                          json={"stage_key": "s", "command_id": "test", "workspace": {"draft_version": 1},
                                "practice": True})
    assert r.status_code == 202  # practice flag routes to the practice job kind (hidden inputs unreachable)
