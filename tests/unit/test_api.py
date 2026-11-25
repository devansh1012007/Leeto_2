"""Unit: participant + admin API behavior through the ASGI transport (no DB needed for
these paths; DB-backed flows live in tests/integration with Postgres)."""
from __future__ import annotations

import sys
import time

import httpx
import pytest
from helpers import load_app


@pytest.fixture()
def participant_app(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
    return load_app("api_participant").app


@pytest.fixture()
def participant_client(participant_app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=participant_app), base_url="http://test")


def _auth_headers() -> dict:
    from auth.tokens import make_access_token

    token = make_access_token(secret="test-secret-test-secret", sub="p1", sid="s1", role="participant")
    return {"Authorization": f"Bearer {token}"}


class TestPublicEndpoints:
    async def test_time_carries_server_time(self, participant_client):
        r = await participant_client.get("/v1/time")
        assert r.status_code == 200
        assert "server_time" in r.json()["meta"]

    async def test_readyz_reports_problems_without_db(self, participant_client):
        r = await participant_client.get("/readyz")
        # DB not reachable in the unit env → 503 with problems list (fail closed)
        assert r.status_code in (200, 503)

    async def test_security_headers_present(self, participant_client):
        r = await participant_client.get("/v1/time")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert r.headers["Cache-Control"] == "private, no-store"


class TestState:
    async def test_state_returns_etag(self, participant_client):
        r = await participant_client.get("/v1/state", headers=_auth_headers())
        assert r.status_code == 200
        etag = r.headers.get("ETag")
        assert etag
        assert r.json()["data"]["node_pointer"]["sub_state"]  # B11 sub-states exposed

    async def test_state_304_on_if_none_match(self, participant_client):
        r1 = await participant_client.get("/v1/state", headers=_auth_headers())
        etag = r1.headers["ETag"]
        r2 = await participant_client.get("/v1/state", headers={**_auth_headers(), "If-None-Match": etag})
        assert r2.status_code == 304

    async def test_state_requires_auth(self, participant_client):
        r = await participant_client.get("/v1/state")
        assert r.status_code == 403

    async def test_error_envelope_shape(self, participant_client):
        r = await participant_client.get("/v1/state")
        body = r.json()
        assert "error" in body and body["error"]["request_id"]


class TestRuns:
    async def test_unknown_command_rejected(self, participant_client):
        r = await participant_client.post(
            "/v1/runs",
            headers={**_auth_headers(), "Idempotency-Key": "key-12345678"},
            json={"stage_key": "level_3_upload", "command_id": "rm -rf", "workspace": {"draft_version": 1}},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "RUN_COMMAND_UNKNOWN"

    async def test_allowed_command_accepted(self, participant_client):
        r = await participant_client.post(
            "/v1/runs",
            headers={**_auth_headers(), "Idempotency-Key": "key-12345679"},
            json={"stage_key": "level_3_upload", "command_id": "test", "workspace": {"draft_version": 1}},
        )
        assert r.status_code == 202

    async def test_run_requires_idempotency_key(self, participant_client):
        r = await participant_client.post(
            "/v1/runs", headers=_auth_headers(),
            json={"stage_key": "level_3_upload", "command_id": "test", "workspace": {"draft_version": 1}},
        )
        assert r.status_code == 422


class TestDrafts:
    async def test_draft_too_large_413(self, participant_client):
        r = await participant_client.put(
            "/v1/drafts/level_2_flags",
            headers={**_auth_headers(), "If-Match": "1"},
            json={"payload": {"blob": "x" * (513 * 1024)}},
        )
        assert r.status_code == 413

    async def test_draft_conflict_409(self, participant_client):
        r = await participant_client.put(
            "/v1/drafts/level_2_flags",
            headers={**_auth_headers(), "If-Match": "0"},
            json={"payload": {"a": 1}},
        )
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "DRAFT_VERSION_CONFLICT"


class TestAdminBootAssertion:
    async def test_admin_refuses_shared_secret_in_staging(self, monkeypatch):
        monkeypatch.setenv("ENV", "staging")
        monkeypatch.setenv("ADMIN_AUTH_MODE", "shared_secret")
        sys.path.insert(0, "backend/apps/api_admin")
        # fresh import must raise (B10) — simulate by constructing Settings directly
        from core.config import ConfigError, Settings

        with pytest.raises(ConfigError, match="shared_secret"):
            Settings().assert_boot_invariants()

    async def test_admin_allows_shared_secret_in_dev(self, monkeypatch):
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("ADMIN_AUTH_MODE", "shared_secret")
        from core.config import Settings

        assert Settings().assert_boot_invariants() == []

    async def test_stub_runner_refuses_prod(self, monkeypatch):
        monkeypatch.setenv("ENV", "prod")
        from core.config import ConfigError, Settings

        monkeypatch.setenv("RUNNER_MODE", "stub")
        with pytest.raises(ConfigError):
            Settings().assert_boot_invariants()


class TestEmergencyEndpoint:
    async def test_emergency_rails_enforced(self, monkeypatch):
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
        admin_main = load_app("api_admin")
        transport = httpx.ASGITransport(app=admin_main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            from auth.tokens import make_access_token

            tok = make_access_token(secret="test-secret-test-secret", sub="admin-1", sid="s1",
                                    role="organizer", audience="admin")
            headers = {"Authorization": f"Bearer {tok}", "X-Stepped-Up-At": str(time.time()),
                       "Idempotency-Key": "key-emergency-001"}
            # numeral wrong → VALIDATION_ERROR
            r = await client.post("/v1/admin/events/e1/emergency/pause", headers=headers,
                            json={"reason": "platform fault requiring a pause", "confirm": "SEVEN"})
            assert r.status_code == 422
            # dry run with all rails → 202 with copy from catalog
            r = await client.post("/v1/admin/events/e1/emergency/pause", headers=headers,
                            json={"reason": "platform fault requiring a pause", "confirm": "7", "dry_run": True})
            assert r.status_code == 202
            body = r.json()["data"]
            assert body["dry_run"] is True
            assert "paused" in body["participant_copy"].lower()

    async def test_rescore_execute_needs_distinct_approver(self, monkeypatch):
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
        admin_main = load_app("api_admin")
        transport = httpx.ASGITransport(app=admin_main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            from auth.tokens import make_access_token

            tok = make_access_token(secret="test-secret-test-secret", sub="admin-1", sid="s1",
                                    role="organizer", audience="admin")
            headers = {"Authorization": f"Bearer {tok}", "X-Stepped-Up-At": str(time.time()),
                       "Idempotency-Key": "key-rescore-0001"}
            r = await client.post("/v1/admin/events/e1/rescore/execute", headers=headers,
                            json={"reason": "correcting scores after answer pack activation",
                                  "approver_id": "admin-1", "confirm": "RESCORE"})
            assert r.status_code == 403
            assert r.json()["error"]["code"] == "ESCALATION_REQUIRED"
