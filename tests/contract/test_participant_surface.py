"""Contract coverage for the full participant API surface: every participant-facing
OpenAPI operation is implemented and returns its documented response shape (Phase 3 gate
"contract tests green for every endpoint")."""
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


def _auth() -> dict:
    from auth.tokens import make_access_token

    token = make_access_token(secret="test-secret-test-secret", sub="p1", sid="s1", role="participant")
    return {"Authorization": f"Bearer {token}"}


def _idem() -> dict:
    return {"Idempotency-Key": "idem-contract-1"}


class TestAuthLifecycle:
    async def test_refresh_fail_closed(self, client):
        r = await client.post("/v1/auth/refresh")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "AUTH_SESSION_EXPIRED"

    async def test_activate_validates_password(self, client):
        r = await client.post("/v1/auth/activate", headers=_idem(),
                              json={"token": "t", "password": "short"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_activate_unknown_token(self, client):
        r = await client.post("/v1/auth/activate", headers=_idem(),
                              json={"token": "t", "password": "long-enough-password"})
        assert r.status_code == 404

    async def test_reset_request_never_enumerates(self, client):
        r = await client.post("/v1/auth/reset/request", headers=_idem(),
                              json={"email": "nobody@example.com"})
        assert r.status_code == 200
        assert r.json()["data"]["accepted"] is True

    async def test_reset_confirm_validates_password(self, client):
        r = await client.post("/v1/auth/reset/confirm", headers=_idem(),
                              json={"token": "t", "password": "short"})
        assert r.status_code == 422


class TestConsentAndContent:
    async def test_consent_get(self, client):
        r = await client.get("/v1/consent", headers=_auth())
        assert r.status_code == 200
        assert "versions" in r.json()["data"]

    async def test_consent_post_requires_versions(self, client):
        r = await client.post("/v1/consent", headers={**_auth(), **_idem()}, json={"versions": {}})
        assert r.status_code == 422
        r2 = await client.post("/v1/consent", headers={**_auth(), **_idem()},
                               json={"versions": {"rules": "2026-11-01"}})
        assert r2.status_code == 200

    async def test_event_details_public(self, client):
        r = await client.get("/v1/content/event-details")
        assert r.status_code == 200
        assert len(r.json()["data"]["sections"]) >= 3


class TestAnnouncementsLeaderboard:
    async def test_announcements_empty(self, client):
        r = await client.get("/v1/announcements", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    async def test_leaderboard_snapshot(self, client):
        r = await client.get("/v1/leaderboard", headers=_auth())
        assert r.status_code == 200
        assert "version" in r.json()["data"]

    async def test_leaderboard_304_on_same_version(self, client):
        r1 = await client.get("/v1/leaderboard", headers=_auth())
        version = r1.json()["data"]["version"]
        r2 = await client.get("/v1/leaderboard", headers=_auth(), params={"since": version})
        assert r2.status_code == 304

    async def test_leaderboard_requires_auth(self, client):
        r = await client.get("/v1/leaderboard")
        assert r.status_code == 403


class TestReceiptsResultsDisputes:
    async def test_receipt_shape(self, client):
        r = await client.get("/v1/receipts/rc-1", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "received"

    async def test_results_not_finalized(self, client):
        r = await client.get("/v1/results", headers=_auth())
        assert r.status_code == 404

    async def test_dispute_validation(self, client):
        r = await client.post("/v1/disputes", headers={**_auth(), **_idem()},
                              json={"subject_type": "award_unit", "subject_id": "u1",
                                    "statement": "short"})
        assert r.status_code == 422

    async def test_dispute_accepted(self, client):
        r = await client.post("/v1/disputes", headers={**_auth(), **_idem()},
                              json={"subject_type": "award_unit", "subject_id": "u1",
                                    "statement": "The awarded points miss a confirmed flag."})
        assert r.status_code == 202
        assert r.json()["data"]["status"] == "open"

    async def test_disputes_list(self, client):
        r = await client.get("/v1/disputes", headers=_auth())
        assert r.status_code == 200


class TestTeam:
    async def test_team_missing_in_stub(self, client):
        r = await client.get("/v1/team", headers=_auth())
        assert r.status_code == 404

    async def test_team_score(self, client):
        r = await client.get("/v1/team/score", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["score"] == 0

    async def test_repo_lock_requires_confirm(self, client):
        r = await client.post("/v1/team/repo-lock", headers={**_auth(), **_idem()},
                              json={"option": "option_a", "confirm": False})
        assert r.status_code == 422

    async def test_repo_lock_locks(self, client):
        r = await client.post("/v1/team/repo-lock", headers={**_auth(), **_idem()},
                              json={"option": "option_a", "confirm": True})
        assert r.status_code == 200
        assert r.json()["data"]["locked"] is True

    async def test_repo_lock_get(self, client):
        r = await client.get("/v1/team/repo-lock", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["locked"] is False


class TestGateDraftsRuns:
    async def test_stage_gate(self, client):
        r = await client.get("/v1/stages/level_2_flags/gate", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["allowed"] is True

    async def test_stage_gate_unknown(self, client):
        r = await client.get("/v1/stages/nonsense/gate", headers=_auth())
        assert r.status_code == 404

    async def test_draft_get(self, client):
        r = await client.get("/v1/drafts/level_2_flags", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["version"] == 1

    async def test_run_cancel(self, client):
        create = await client.post("/v1/runs", headers={**_auth(), **_idem()},
                                   json={"stage_key": "level_3_upload", "command_id": "build",
                                         "workspace": {}})
        assert create.status_code == 202
        run_id = create.json()["data"]["id"]
        r = await client.post(f"/v1/runs/{run_id}/cancel", headers={**_auth(), **_idem()})
        assert r.status_code == 202
        assert r.json()["data"]["state"] == "cancelling"

    async def test_run_cancel_unknown(self, client):
        r = await client.post("/v1/runs/nope/cancel", headers={**_auth(), **_idem()})
        assert r.status_code == 404


class TestRepoBrowser:
    async def test_repo_tree(self, client):
        r = await client.get("/v1/repo/tree", headers=_auth())
        assert r.status_code == 200
        assert "src/auth/session.py" in r.json()["data"]["files"]

    async def test_repo_file(self, client):
        r = await client.get("/v1/repo/files/src/auth/session.py", headers=_auth())
        assert r.status_code == 200
        assert "verify_session" in r.json()["data"]["content"]

    async def test_repo_file_not_found(self, client):
        r = await client.get("/v1/repo/files/src/nope.py", headers=_auth())
        assert r.status_code == 404

    async def test_repo_search(self, client):
        r = await client.get("/v1/repo/search", headers=_auth(), params={"q": "verify"})
        assert r.status_code == 200
        assert len(r.json()["data"]["hits"]) >= 1

    async def test_repo_search_query_too_short(self, client):
        r = await client.get("/v1/repo/search", headers=_auth(), params={"q": "v"})
        assert r.status_code == 422


class TestUploads:
    async def test_upload_delete(self, client):
        r = await client.delete("/v1/uploads/00000000-0000-0000-0000-000000000002",
                                headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["deleted"] is True


class TestPractice:
    async def test_practice_state(self, client):
        r = await client.get("/v1/practice/state", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["enabled"] is True

    async def test_practice_file(self, client):
        r = await client.get("/v1/practice/files/src/README.md", headers=_auth())
        assert r.status_code == 200

    async def test_practice_run_queued(self, client):
        r = await client.post("/v1/practice/runs", headers={**_auth(), **_idem()},
                              json={"language": "python", "files": {"main.py": "print(1)"}})
        assert r.status_code == 202
        assert r.json()["data"]["state"] == "queued"
