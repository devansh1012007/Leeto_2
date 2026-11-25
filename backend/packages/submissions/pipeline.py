"""Submit transaction (B6 + 02 §9.5) — the correctness-critical path.

Lock order (always the same, to avoid deadlocks):
  idempotency → stage state → clock_timestamp() once → team/participant → quota → writes.

All writes land in ONE transaction: submission, flags (or artifact), evaluation_event,
job:evaluate, outbox, audit chain entry. 202 with receipt. Idempotent replay returns the
original 202 EVEN AFTER THE DEADLINE (B4/R-15).
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Any

from core.errors import ApiError
from db.session import payload_hash
from sqlalchemy import text

REPLAY_ROUTES = {"submit", "repo_lock", "upload", "run", "force_action"}  # event + 7 days (B4)


@dataclass
class SubmitOutcome:
    receipt_id: str
    accepted_at: str
    replay: bool = False


def receipt_code(submission_id: str, accepted_at: str) -> str:
    """Short receipt derived from an HMAC so organizers can verify participant receipts (10.4)."""
    from core.config import get_settings

    key = (get_settings().jwt_secret or "dev-only").encode()
    mac = hmac.new(key, f"{submission_id}:{accepted_at}".encode(), hashlib.sha256).hexdigest()
    return f"{mac[:4].upper()}-{{mac[4:8].upper()}}" if False else f"{mac[:4].upper()}-{mac[4:8].upper()}"


def _stage_row(conn, stage_key: str, event_id: str):
    return conn.execute(
        text("SELECT id, kind, exec_opens_at, exec_closes_at, caps FROM app.stages "
             "WHERE stage_key = :k AND event_id = :e"),
        {"k": stage_key, "e": event_id},
    ).first()


def _progress_row(conn, participant_id: str, event_id: str):
    return conn.execute(
        text("SELECT node, sub_state, version FROM app.participant_progress "
             "WHERE participant_id = :p AND event_id = :e FOR UPDATE"),
        {"p": participant_id, "e": event_id},
    ).first()


async def submit_stage(conn, *, participant_id: str, team_id: str | None, event_id: str,
                       stage_key: str, kind: str, body: dict[str, Any],
                       idempotency_key: str, auto: bool = False) -> SubmitOutcome:
    """The full submit transaction body. `conn` must be inside an open transaction."""
    ph = payload_hash(body)

    # ---- 1. idempotency reserve (lock order #1)
    existing = conn.execute(
        text("SELECT response_status, response_body, payload_hash FROM app.idempotency "
             "WHERE participant_id = :p AND route = 'submit' AND key = :k"),
        {"p": participant_id, "k": idempotency_key},
    ).first()
    if existing:
        if existing.payload_hash != ph:
            raise ApiError("IDEMPOTENCY_CONFLICT")
        stored = existing.response_body or {}
        return SubmitOutcome(
            receipt_id=stored.get("receipt_id", ""),
            accepted_at=stored.get("accepted_at", ""),
            replay=True,
        )

    # ---- 2. lock the stage-state row (lock order #2)
    stage = _stage_row(conn, stage_key, event_id)
    if stage is None:
        raise ApiError("NOT_FOUND")
    stage_id, stage_kind, exec_opens_at, exec_closes_at, caps = stage

    # already submitted? (unique constraint is the backstop)
    dup = conn.execute(
        text("SELECT receipt_code FROM app.submissions WHERE participant_id = :p AND stage_id = :s"),
        {"p": participant_id, "s": stage_id},
    ).first()
    if dup:
        raise ApiError("ALREADY_SUBMITTED")

    # ---- 3. clock ONCE after the stage lock (lock order #3) — B6/ADR-012
    now = (await _clock(conn)) if False else conn.execute(text("SELECT clock_timestamp()")).scalar_one()

    # paused / closed checks against the authoritative clock
    ev = conn.execute(
        text("SELECT paused, safe_mode FROM app.events WHERE id = :e"), {"e": event_id}
    ).first()
    if ev and ev.paused:
        raise ApiError("STAGE_PAUSED")
    if exec_opens_at is not None and now < exec_opens_at:
        raise ApiError("STAGE_NOT_OPEN")
    grace_s = float((caps or {}).get("grace_s", 3))
    if exec_closes_at is not None and now > exec_closes_at and not auto:
        raise ApiError("STAGE_CLOSED")
    if auto and exec_closes_at is not None and now > _add_seconds(exec_closes_at, grace_s + 60):
        # auto-submit path gets exactly the documented grace (02 §12), never more
        raise ApiError("STAGE_CLOSED")

    # ---- 4. participant/team progress lock (lock order #4)
    progress = _progress_row(conn, participant_id, event_id)
    if progress is None:
        raise ApiError("NOT_FOUND")

    # ---- 5. quota lock (lock order #5)
    q = conn.execute(
        text("SELECT buckets FROM app.quota WHERE participant_id = :p FOR UPDATE"),
        {"p": participant_id},
    ).first()
    buckets = (q.buckets if q else {}) or {}
    submits = buckets.get("submits_this_minute", 0)
    if not auto and submits >= 6:
        raise ApiError("SUBMISSION_CAP_REACHED", details={"retry_after": 60})
    buckets["submits_this_minute"] = submits + 1
    conn.execute(
        text("INSERT INTO app.quota (participant_id, limits, buckets) VALUES (:p, '{}', :b) "
             "ON CONFLICT (participant_id) DO UPDATE SET buckets = :b, updated_at = now()"),
        {"p": participant_id, "b": buckets if isinstance(buckets, dict) else __import__("json").dumps(buckets)},
    )

    # ---- 6. domain validation + writes (lock order #6)
    if kind == "flags":
        flags = body.get("flags") or []
        if not flags:
            raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "flags", "problem": "min 1"}]})
        for f in flags:
            _validate_flag(f, caps or {})
    elif kind == "upload":
        upload_id = body.get("upload_id")
        if not upload_id:
            raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "upload_id", "problem": "required"}]})
    else:
        raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "kind", "problem": "flags|upload"}]})

    submission_id = str(uuid.uuid4())
    accepted_at = now.isoformat()
    code = receipt_code(submission_id, accepted_at)
    conn.execute(
        text("INSERT INTO app.submissions (id, tenant_id, participant_id, team_id, stage_id, kind, status, "
             "receipt_code, accepted_at, auto_submitted) "
             "VALUES (:id, (SELECT tenant_id FROM app.events WHERE id = :e), :p, :t, :s, :kind, 'received', "
             ":rc, :at, :auto)"),
        {"id": submission_id, "e": event_id, "p": participant_id, "t": team_id, "s": stage_id,
         "kind": kind, "rc": code, "at": now, "auto": auto},
    )
    if kind == "flags":
        import json as _json
        for i, f in enumerate(flags):
            conn.execute(
                text("INSERT INTO app.flags (id, tenant_id, submission_id, ordinal, locations, explanation, category) "
                     "VALUES (:id, (SELECT tenant_id FROM app.events WHERE id = :e), :sub, :ord, :loc, :exp, :cat)"),
                {"id": str(uuid.uuid4()), "e": event_id, "sub": submission_id, "ord": i,
                 "loc": _json.dumps(f.get("locations") or [{"file": f.get("file"), "lines": f.get("lines")}]),
                 "exp": f.get("explanation"), "cat": f.get("category")},
            )
    else:
        conn.execute(
            text("UPDATE app.submission_artifacts SET submission_id = :sub WHERE id = :up AND submission_id IS NULL"),
            {"sub": submission_id, "up": body["upload_id"]},
        )

    # evaluation_event + job + outbox + audit — same TX (B6 step 13)
    conn.execute(
        text("INSERT INTO app.evaluation_events (submission_id, kind, payload) VALUES (:s, 'matcher', :p)"),
        {"s": submission_id, "p": '{"state":"queued"}'},
    )
    conn.execute(
        text("INSERT INTO app.jobs (tenant_id, kind, priority, payload, dedupe_key) "
             "VALUES ((SELECT tenant_id FROM app.events WHERE id = :e), 'evaluate', 0, :p, :dk)"),
        {"e": event_id, "p": f'{{"submission_id":"{submission_id}"}}', "dk": f"evaluate:{submission_id}"},
    )
    conn.execute(
        text("INSERT INTO app.outbox (kind, payload) VALUES ('submission_accepted', :p)"),
        {"p": f'{{"submission_id":"{submission_id}","participant_id":"{participant_id}"}}'},
    )
    conn.execute(
        text("INSERT INTO audit.entries (event_id, actor_id, actor_role, action, target_type, target_id) "
             "VALUES (:e, :p, 'participant', 'submission.accepted', 'submission', :s)"),
        {"e": event_id, "p": participant_id, "s": submission_id},
    )
    # store the idempotent response (replayable even after deadline — B4)
    conn.execute(
        text("INSERT INTO app.idempotency (participant_id, route, key, payload_hash, response_status, response_body, expires_at) "
             "VALUES (:p, 'submit', :k, :ph, 202, :rb, now() + interval '7 days')"),
        {"p": participant_id, "k": idempotency_key, "ph": ph,
         "rb": f'{{"receipt_id":"{code}","accepted_at":"{accepted_at}","status":"received"}}'},
    )
    # advance the node pointer forward (sub_state transitions in code, not DB — B11)
    _advance_node(conn, participant_id, event_id, stage_key)

    return SubmitOutcome(receipt_id=code, accepted_at=accepted_at)


def _add_seconds(ts, seconds: float):
    import datetime as _dt

    return ts + _dt.timedelta(seconds=seconds)


def _validate_flag(flag: dict, caps: dict) -> None:
    max_span = int(caps.get("max_span", 25))
    file = flag.get("file")
    lines = str(flag.get("lines", ""))
    if not file or not lines:
        raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "flags", "problem": "file+lines required"}]})
    start, _, end = lines.partition("-")
    try:
        s, e = int(start), int(end or start)
    except ValueError:
        raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "lines", "problem": "bad range"}]}) from None
    if s > e or (e - s + 1) > max_span:
        raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "lines", "problem": f"span ≤ {max_span}"}]})
    if not (flag.get("explanation") or "").strip():
        raise ApiError("SUBMISSION_INVALID", details={"fields": [{"field": "explanation", "problem": "required"}]})


def _advance_node(conn, participant_id: str, event_id: str, stage_key: str) -> None:
    """Forward-only pointer move; sub_state → submitting|evaluating (display-level, B11)."""
    conn.execute(
        text("UPDATE app.participant_progress "
             "SET node = CASE "
             "  WHEN node LIKE 'L%' AND node NOT LIKE '%SUBMITTED' AND node <> 'LANDING' "
             "      AND node NOT LIKE '%EXPLAIN' THEN replace(node, '_EXEC', '_SUBMITTED') "
             "  WHEN node LIKE '%EXPLAIN' THEN replace(node, 'EXPLAIN', 'EXEC') "
             "  ELSE node END, "
             "     sub_state = 'evaluating', version = version + 1, updated_at = now() "
             "WHERE participant_id = :p AND event_id = :e"),
        {"p": participant_id, "e": event_id},
    )


def _clock(conn):  # pragma: no cover — async path kept for API parity
    return conn.execute(text("SELECT clock_timestamp()")).scalar_one()


# ---------------------------------------------------------------- force-advance (R-23/D.2)
async def force_advance(conn, *, event_id: str, team_id: str, to_node: str, actor_id: str,
                        reason: str, autosubmit_fn=None) -> dict:
    """Force-advance first runs auto-submit for the pending level (R-23/D.2), then moves
    the pointer and sets adjusted_by/adjusted_reason. Participant sees 'Adjusted by organizer'."""
    if len(reason) < 10:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 10 chars"}]})
    members = conn.execute(
        text("SELECT user_id FROM app.team_members WHERE team_id = :t"), {"t": team_id}
    ).fetchall()
    advanced = []
    for (uid,) in members:
        pending = conn.execute(
            text("SELECT s.stage_key FROM app.stages s "
                 "JOIN app.participant_progress pp ON pp.event_id = s.event_id AND pp.participant_id = :u "
                 "WHERE s.event_id = :e AND pp.node LIKE '%EXEC' "
                 "AND NOT EXISTS (SELECT 1 FROM app.submissions sub WHERE sub.participant_id = :u AND sub.stage_id = s.id) "
                 "ORDER BY s.ordinal LIMIT 1"),
            {"u": uid, "e": event_id},
        ).first()
        if pending and autosubmit_fn is not None:
            await autosubmit_fn(conn, participant_id=str(uid), event_id=event_id,
                                stage_key=pending[0], auto=True)
        conn.execute(
            text("UPDATE app.participant_progress SET node = :n, sub_state = 'adjusted', "
                 "adjusted_by = :a, adjusted_reason = :r, version = version + 1, updated_at = now() "
                 "WHERE participant_id = :u AND event_id = :e"),
            {"n": to_node, "a": actor_id, "r": reason, "u": uid, "e": event_id},
        )
        advanced.append(str(uid))
    conn.execute(
        text("INSERT INTO audit.entries (event_id, actor_id, actor_role, action, target_type, target_id, details) "
             "VALUES (:e, :a, 'organizer', 'team.force_advance', 'team', :t, :d)"),
        {"e": event_id, "a": actor_id, "t": team_id, "d": f'{{"to_node":"{to_node}","reason":"{reason}"}}'},
    )
    return {"advanced": advanced}
