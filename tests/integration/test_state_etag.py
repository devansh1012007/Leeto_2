"""State ETag gate (R-09/B8): ETag + 304 on If-None-Match; version-keyed body.
Primary e2e coverage: tests/unit/test_api.py::TestState."""
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


async def test_etag_and_304(client):
    r1 = await client.get("/v1/state", headers=_auth())
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag, "state must carry an ETag (R-09/B8)"
    r2 = await client.get("/v1/state", headers={**_auth(), "If-None-Match": etag})
    assert r2.status_code == 304
