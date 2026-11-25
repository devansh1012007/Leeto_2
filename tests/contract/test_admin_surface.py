"""Contract coverage for the admin API surface: step-up rails, two-approver rule, typed
confirmations, reason minimums, and role restrictions (RBAC: gt role for ground truth,
reviewer role for review decisions)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helpers import load_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret")
    app = load_app("api_admin").app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _auth(role: str = "admin", sub: str = "admin-1") -> dict:
    from auth.tokens import make_access_token

    token = make_access_token(secret="test-secret-test-secret", sub=sub, sid="sa", role=role,
                              audience="admin")
    return {"Authorization": f"Bearer {token}"}


def _stepped(auth: dict) -> dict:
    return {**auth, "X-Stepped-Up-At": str(time.time())}


def _idem() -> dict:
    return {"Idempotency-Key": "idem-admin-1"}


class TestEventsLifecycle:
    async def test_events_list(self, client):
        r = await client.get("/v1/admin/events", headers=_auth())
        assert r.status_code == 200

    async def test_events_create(self, client):
        r = await client.post("/v1/admin/events", headers={**_stepped(_auth()), **_idem()},
                              json={"name": "Bug Hunt 2027", "slug": "bh-2027", "tz": "Asia/Kolkata"})
        assert r.status_code == 201
        assert r.json()["data"]["status"] == "draft"

    async def test_events_create_requires_step_up(self, client):
        r = await client.post("/v1/admin/events", headers={**_auth(), **_idem()},
                              json={"name": "Bug Hunt 2027", "slug": "bh-2027", "tz": "Asia/Kolkata"})
        assert r.status_code == 403

    async def test_finalize_typed_confirm(self, client):
        r = await client.post("/v1/admin/events/e1/finalize", headers={**_stepped(_auth()), **_idem()},
                              json={"confirm": "yes"})
        assert r.status_code == 422
        r2 = await client.post("/v1/admin/events/e1/finalize",
                               headers={**_stepped(_auth()), **_idem()},
                               json={"confirm": "FINALIZE", "approver_id": "admin-2"})
        assert r2.status_code == 200
        assert r2.json()["data"]["leaderboard_frozen"] is True

    async def test_leaderboard_mode(self, client):
        r = await client.post("/v1/admin/events/e1/leaderboard/mode",
                              headers={**_stepped(_auth()), **_idem()},
                              json={"mode": "frozen", "reason": "finalize freeze window"})
        assert r.status_code == 200
        assert r.json()["data"]["mode"] == "frozen"

    async def test_switches_get(self, client):
        r = await client.get("/v1/admin/events/e1/switches", headers=_auth())
        assert r.status_code == 200
        assert "leaderboard" in r.json()["data"]["switches"]

    async def test_announcement_validation(self, client):
        r = await client.post("/v1/admin/events/e1/announcements",
                              headers={**_stepped(_auth()), **_idem()},
                              json={"severity": "loud", "body_md": "hello"})
        assert r.status_code == 422
        r2 = await client.post("/v1/admin/events/e1/announcements",
                               headers={**_stepped(_auth()), **_idem()},
                               json={"severity": "info", "body_md": "Round 2 begins at 10:00."})
        assert r2.status_code == 201

    async def test_stage_extend_bounds(self, client):
        r = await client.post("/v1/admin/stages/s1/extend", headers={**_stepped(_auth()), **_idem()},
                              json={"minutes": 0, "reason": "extend the stage window"})
        assert r.status_code == 422
        r2 = await client.post("/v1/admin/stages/s1/extend",
                               headers={**_stepped(_auth()), **_idem()},
                               json={"minutes": 10, "reason": "runner outage compensation"})
        assert r2.status_code == 200

    async def test_team_advance_correction_protocol(self, client):
        r = await client.post("/v1/admin/events/e1/teams/t1/advance",
                              headers={**_stepped(_auth()), **_idem()},
                              json={"to_node": "L2_EXEC", "reason": "missed transition timer"})
        assert r.status_code == 200
        data = r.json()["data"]["node_pointer"]
        assert data["adjusted_by"] == "admin-1"
        assert data["adjusted_reason"]


class TestGroundTruthRole:
    async def test_gt_get_requires_gt_role(self, client):
        r = await client.get("/v1/admin/challenges/c1/ground-truth", headers=_auth("admin"))
        assert r.status_code == 403
        r2 = await client.get("/v1/admin/challenges/c1/ground-truth", headers=_auth("ground_truth"))
        assert r2.status_code == 200

    async def test_gt_put_validates_bugs(self, client):
        r = await client.put("/v1/admin/challenges/c1/ground-truth",
                             headers={**_stepped(_auth("ground_truth", "gt-1")), **_idem()},
                             json={"bugs": []})
        assert r.status_code == 422
        r2 = await client.put("/v1/admin/challenges/c1/ground-truth",
                              headers={**_stepped(_auth("ground_truth", "gt-1")), **_idem()},
                              json={"bugs": [{"file": "src/a.py", "lines": "1-2"}]})
        assert r2.status_code == 200


class TestReviewRole:
    async def test_review_claim_requires_reviewer(self, client):
        r = await client.post("/v1/admin/review/r1/claim", headers=_auth("admin"))
        assert r.status_code == 403
        r2 = await client.post("/v1/admin/review/r1/claim", headers=_auth("reviewer"))
        assert r2.status_code == 200

    async def test_review_decide_paths(self, client):
        r = await client.post("/v1/admin/review/r1/decide",
                              headers={**_stepped(_auth("reviewer", "rev-1")), **_idem()},
                              json={"decision": "maybe", "reason": "undecided about the award"})
        assert r.status_code == 422
        r2 = await client.post("/v1/admin/review/r1/decide",
                               headers={**_stepped(_auth("reviewer", "rev-1")), **_idem()},
                               json={"decision": "accept", "reason": "confirmed flag matches GT",
                                     "points": 100, "ai_override": True})
        assert r2.status_code == 200
        assert r2.json()["data"]["ai_override"] is True


class TestIncidents:
    async def test_incident_lifecycle(self, client):
        r = await client.post("/v1/admin/incidents/i1/assign", headers={**_auth(), **_idem()},
                              json={"commander_id": "admin-2"})
        assert r.status_code == 200
        r2 = await client.post("/v1/admin/incidents/i1/step", headers={**_auth(), **_idem()},
                               json={"runbook_id": "RB-01", "step": "rollback", "status": "done"})
        assert r2.status_code == 200
        r3 = await client.post("/v1/admin/incidents/i1/resolve",
                               headers={**_stepped(_auth()), **_idem()},
                               json={"resolution": "rolled back the bad deploy; verified healthy"})
        assert r3.status_code == 200

    async def test_resolve_requires_step_up(self, client):
        r = await client.post("/v1/admin/incidents/i1/resolve", headers={**_auth(), **_idem()},
                              json={"resolution": "rolled back the bad deploy; verified healthy"})
        assert r.status_code == 403


class TestExportsAudit:
    async def test_export_queued(self, client):
        r = await client.post("/v1/admin/exports", headers={**_stepped(_auth()), **_idem()},
                              json={"kind": "results"})
        assert r.status_code == 202

    async def test_export_kind_validated(self, client):
        r = await client.post("/v1/admin/exports", headers={**_stepped(_auth()), **_idem()},
                              json={"kind": "everything"})
        assert r.status_code == 422

    async def test_audit_verify(self, client):
        r = await client.post("/v1/admin/audit/verify", headers=_stepped(_auth()))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "verified"

    async def test_admin_health(self, client):
        r = await client.get("/v1/admin/health", headers=_auth())
        assert r.status_code == 200
        assert r.json()["data"]["api"] == "ok"

    async def test_disputes_list(self, client):
        r = await client.get("/v1/admin/disputes", headers=_auth())
        assert r.status_code == 200
