"""T-3.x gates: submit pipeline — lock order (B6), idempotency replay after deadline (B4).

Uses the fake DB to exercise the SERVICE logic; Postgres behavior (unique indexes,
FOR UPDATE semantics) is covered by the CI integration job.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

PAST = datetime(2020, 1, 1, tzinfo=UTC)
FUTURE = datetime(2030, 1, 1, tzinfo=UTC)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from core.errors import ApiError
from fake_db import FakeConn
from submissions.pipeline import submit_stage

EVENT = "00000000-0000-0000-0000-000000000001"
PARTICIPANT = "p-1"


def _body(flags=None):
    return {"kind": "flags", "flags": flags or [
        {"file": "src/auth.py", "lines": "41-47", "explanation": "non-constant-time compare leaks timing"}
    ]}


async def _run(conn: FakeConn, key: str = "key-12345678", body=None, auto=False):
    return await submit_stage(
        conn, participant_id=PARTICIPANT, team_id=None, event_id=EVENT,
        stage_key="level_2_flags", kind="flags", body=body or _body(),
        idempotency_key=key, auto=auto,
    )


class TestLockOrder:
    async def test_idempotency_reserved_before_stage_lock(self):
        conn = FakeConn()
        await _run(conn)
        # the idempotency CHECK must precede every FOR UPDATE lock (B6 lock order #1);
        # the response INSERT lands with the other writes in the same TX.
        first_idem = next(
            i for i, (sql, _) in enumerate(conn.executed)
            if "FROM app.idempotency" in sql and "SELECT" in sql
        )
        first_lock = next(
            (i for i, (sql, _) in enumerate(conn.executed) if "FOR UPDATE" in sql),
            len(conn.executed),
        )
        assert first_idem < first_lock, "B6: idempotency check must come before any row lock"

    async def test_progress_lock_before_quota_lock(self):
        conn = FakeConn()
        await _run(conn)
        assert conn.locks_taken.index("progress") < conn.locks_taken.index("quota"), \
            "B6: team/participant progress lock precedes quota lock"


class TestIdempotency:
    async def test_replay_returns_original_receipt(self):
        conn = FakeConn()
        first = await _run(conn, key="key-replay-01")
        conn.exec_closes_at = PAST  # deadline now long past
        replay = await _run(conn, key="key-replay-01")
        assert replay.replay is True
        assert replay.receipt_id == first.receipt_id  # even after the deadline (B4)

    async def test_same_key_different_body_conflicts(self):
        from db.session import payload_hash  # noqa: F401

        conn = FakeConn()
        await _run(conn, key="key-conflict-1", body=_body([{"file": "a.py", "lines": "1-2", "explanation": "x" * 50}]))
        with pytest.raises(ApiError) as ei:
            await _run(conn, key="key-conflict-1", body=_body([{"file": "b.py", "lines": "3-4", "explanation": "y" * 50}]))
        assert ei.value.code == "IDEMPOTENCY_CONFLICT"

    async def test_different_key_after_deadline_closed(self):
        conn = FakeConn()
        await _run(conn, key="key-open-1")
        conn.exec_closes_at = PAST
        with pytest.raises(ApiError) as ei:
            await _run(conn, key="key-open-2")
        assert ei.value.code == "STAGE_CLOSED"


class TestDeadlineBoundary:
    async def test_paused_rejects(self):
        conn = FakeConn(paused=True)
        with pytest.raises(ApiError) as ei:
            await _run(conn)
        assert ei.value.code == "STAGE_PAUSED"

    async def test_not_open_rejects(self):
        conn = FakeConn(exec_opens_at=FUTURE)
        with pytest.raises(ApiError) as ei:
            await _run(conn)
        assert ei.value.code == "STAGE_NOT_OPEN"

    async def test_auto_submit_gets_only_the_documented_grace(self):
        conn = FakeConn(exec_closes_at=PAST)
        with pytest.raises(ApiError) as ei:
            await _run(conn, auto=True)
        assert ei.value.code == "STAGE_CLOSED"


class TestValidation:
    async def test_empty_flags_invalid(self):
        conn = FakeConn()
        with pytest.raises(ApiError) as ei:
            await _run(conn, body={"kind": "flags", "flags": []})
        assert ei.value.code == "SUBMISSION_INVALID"

    async def test_span_over_max_invalid(self):
        conn = FakeConn()
        with pytest.raises(ApiError):
            await _run(conn, body=_body([{"file": "a.py", "lines": "1-40", "explanation": "x" * 50}]))
