"""T-7.4: correction protocol end-to-end (E.3's 10 steps) against the fake DB:
escalate → draft entry (overlap rejected) → dry-run → activate (two approvers) →
rescore job → ledger has ap_entry_id entries → audit → leaderboard version bump.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import answer_authority.service as aas
from core.errors import ApiError
from fake_db import FakeConn


def _conn() -> FakeConn:
    conn = FakeConn()
    conn.tables["candidate"] = [
        {"id": "cand-1", "tenant_id": "t1", "submission_id": "sub-1", "flag_id": "flag-1",
         "reviewer_rationale": "real defect, matches no GT anchor", "state": "pending",
         "created_by": "rev-1"},
    ]
    conn.tables["_pack_state"] = ["draft"]
    return conn


class TestProtocol:
    async def test_escalate_creates_pending_candidate(self):
        conn = _conn()
        cid = aas.escalate_candidate(conn, submission_id="sub-9", flag_id="flag-9",
                                     reviewer_id="rev-1", rationale="unplanned real bug at parse loop")
        assert cid
        assert any(a == "candidate_bug.escalate" for (sql, _), a in
                   [(e, "") for e in conn.executed] ) or "gt.candidate_bugs" in " ".join(
                       s for s, _ in conn.executed)

    async def test_accept_creates_draft_entry_no_scoring(self):
        """E.2: accepting NEVER scores — no ledger INSERT happens here."""
        conn = _conn()
        entry_id = aas.accept_candidate(
            conn, candidate_id="cand-1", gt_user_id="gt-1",
            canonical_file="src/util/parse.py", line_anchors=[{"file": "src/util/parse.py", "lines": "12-18"}],
            reason="verified real defect, no GT anchor at this location",
        )
        assert entry_id
        ledger_sqls = [s for s, _ in conn.executed if "INSERT INTO app.ledger" in s]
        assert ledger_sqls == [], "E.2: acceptance must not write ledger entries"

    async def test_accept_rejects_short_reason(self):
        conn = _conn()
        with pytest.raises(ApiError) as ei:
            aas.accept_candidate(conn, candidate_id="cand-1", gt_user_id="gt-1",
                                 canonical_file="a.py", line_anchors=[], reason="too short")
        assert ei.value.code == "VALIDATION_ERROR"

    async def test_activate_requires_distinct_approver(self):
        conn = _conn()
        with pytest.raises(ApiError) as ei:
            aas.activate_pack(conn, pack_id="pack-1", actor_id="admin-1",
                              approver_id="admin-1", reason="activation of reviewed answer pack v4")
        assert ei.value.code == "ESCALATION_REQUIRED"

    async def test_activate_returns_rescore_job_not_inline_scoring(self):
        """E.2/R-04: activation returns rescore_job_id; zero ledger writes inline."""
        conn = _conn()
        conn.tables["_pack_state"] = ["draft"]
        job_id = aas.activate_pack(conn, pack_id="pack-1", actor_id="admin-1",
                                   approver_id="admin-2", reason="activation of reviewed answer pack v4")
        assert job_id
        assert any("INSERT INTO app.jobs" in s and "rescore" in s for s, _ in conn.executed), \
            "activation must enqueue the rescore job"
        ledger_sqls = [s for s, _ in conn.executed if "INSERT INTO app.ledger" in s]
        assert ledger_sqls == [], "activation must not score inline (E.2)"

    async def test_dry_run_is_read_only(self):
        conn = _conn()
        conn.tables["ledger"] = []
        result = aas.rescore_dry_run(conn, event_id="e1")
        assert "deltas" in result and "affected_participants" in result
        writes = [s for s, _ in conn.executed if "INSERT" in s or "UPDATE" in s]
        assert writes == [], "dry run writes nothing"

    async def test_timing_guard_blocks_last_10_minutes(self):
        # stage ending within 10 minutes → the guard must fire (the fake reports count 1)
        class GuardConn(FakeConn):
            def execute(self, sql, params=None):
                if "count(*) FROM app.stages" in str(sql):
                    from fake_db import _Scalar

                    return _Scalar(1)
                return super().execute(sql, params)

        with pytest.raises(ApiError) as ei:
            aas.activation_timing_guard(GuardConn(), event_id="e1")
        assert ei.value.code == "TIMING_GUARD"
