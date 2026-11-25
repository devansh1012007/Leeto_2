"""T-10.8: security headers on every API response (02 §13 / T-3.12)."""
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


async def test_security_headers(client):
    r = await client.get("/v1/time")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age" in r.headers["Strict-Transport-Security"]
    assert r.headers["Cache-Control"] == "private, no-store"  # R-14 posture on API responses


async def test_request_id_on_every_response(client):
    r = await client.get("/v1/time")
    assert r.headers.get("X-Request-Id")


async def test_error_envelope_has_request_id(client):
    r = await client.get("/v1/state")  # unauthenticated
    body = r.json()
    assert body["error"]["request_id"]
