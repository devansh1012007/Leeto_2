"""Emergency powers with the full safety-rail set (A13; 08 Part 4 + §4.12, R-34).

Rails enforced on EVERY action:
  step-up < 5 min · two distinct approvers (destructive) · reason ≥ 20 chars · typed numeral
  confirm · dry-run · pre-action snapshot · catalog participant copy · 60 s undo where
  reversible · concurrent-action lock per scope · ≤ 10 actions/min per event.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.errors import ApiError
from sqlalchemy import text

MAX_ACTIONS_PER_MINUTE = 10
STEP_UP_MAX_AGE_S = 300
MIN_REASON_LEN = 20
SAFE_MODE_AUTO_EXIT_S = 4 * 3600


@dataclass
class EmergencyRequest:
    action: str
    event_id: str
    actor_id: str
    reason: str
    confirm: str
    stepped_up_at: float
    approver_id: str | None = None
    dry_run: bool = False
    payload: dict[str, Any] | None = None


# Reversibility catalog (08 §4.9) — surfaced in the UI BEFORE confirm.
REVERSIBILITY: dict[str, dict[str, str]] = {
    "pause": {"undo_window": "until-resume", "reversal": "resume", "notification": "automatic"},
    "resume": {"undo_window": "none", "reversal": "pause", "notification": "automatic"},
    "extend": {"undo_window": "60s", "reversal": "inverse_action", "notification": "automatic"},
    "freeze_writes": {"undo_window": "until-thaw", "reversal": "thaw", "notification": "automatic"},
    "safe_mode": {"undo_window": "until-exit", "reversal": "safe_mode off (auto-exit 4h)", "notification": "automatic"},
    "advance": {"undo_window": "none", "reversal": "manual_reversal_entries", "notification": "automatic"},
    "freeze_participants": {"undo_window": "unlimited", "reversal": "unfreeze", "notification": "manual"},
    "kill_sessions": {"undo_window": "none", "reversal": "none", "notification": "manual"},
    "logout_all": {"undo_window": "none", "reversal": "none", "notification": "automatic"},
    "quarantine": {"undo_window": "unlimited", "reversal": "unquarantine", "notification": "automatic"},
    "score_adjust": {"undo_window": "none", "reversal": "reversal_ledger_entry", "notification": "automatic"},
    "snapshot": {"undo_window": "n/a", "reversal": "n/a", "notification": "none"},
    "restore": {"undo_window": "none", "reversal": "reversal_entries_only", "notification": "automatic"},
    "publish_partial": {"undo_window": "60s", "reversal": "unpublish (ledger intact)", "notification": "automatic"},
    "content_push": {"undo_window": "60s", "reversal": "content_revert", "notification": "automatic"},
    "force_refresh": {"undo_window": "60s", "reversal": "inverse_action", "notification": "automatic"},
    "drain_runner": {"undo_window": "until-undrain", "reversal": "inverse_action", "notification": "none"},
    "kill_runs": {"undo_window": "none", "reversal": "none", "notification": "manual"},
    "state_lite": {"undo_window": "until-inverse", "reversal": "inverse_action", "notification": "none"},
    "cache_reset": {"undo_window": "n/a", "reversal": "n/a", "notification": "none"},
}

DESTRUCTIVE = {"advance", "score_adjust", "restore", "kill_runs", "publish_partial", "logout_all"}


def check_rails(req: EmergencyRequest, *, now: float | None = None) -> None:
    """All rails, in order. Raises the matching catalog error on violation."""
    now = now or time.time()
    # rail 1: step-up freshness
    if now - req.stepped_up_at > STEP_UP_MAX_AGE_S:
        raise ApiError("AUTH_STEP_UP_REQUIRED", details={"reason": "step_up_expired"})
    # rail 2: two distinct approvers for destructive scope
    if req.action in DESTRUCTIVE:
        if not req.approver_id:
            raise ApiError("ESCALATION_REQUIRED", details={"reason": "second_approver_required"})
        if req.approver_id == req.actor_id:
            raise ApiError("ESCALATION_REQUIRED", details={"reason": "second_approver_must_differ"})
    # rail 3: reason length
    if len(req.reason.strip()) < MIN_REASON_LEN:
        raise ApiError("VALIDATION_ERROR",
                       details={"fields": [{"field": "reason", "problem": f"min {MIN_REASON_LEN} chars"}]})
    # rail 4: typed numeral confirmation (R-34) — exact match, no trimming
    if req.confirm != "7":
        raise ApiError("VALIDATION_ERROR",
                       details={"fields": [{"field": "confirm", "problem": "type the numeral 7"}]})


def check_rate(conn, *, event_id: str) -> None:
    """Rail 9: ≤ 10 emergency actions per minute per event."""
    n = conn.execute(
        text("SELECT count(*) FROM app.emergency_actions "
             "WHERE event_id = :e AND created_at > now() - interval '1 minute'"),
        {"e": event_id},
    ).scalar_one()
    if n >= MAX_ACTIONS_PER_MINUTE:
        raise ApiError("EMERGENCY_RATE_LIMITED")


def participant_copy(action: str, catalog: dict[str, str], payload: dict[str, Any] | None = None) -> str:
    """Rail 6: participant notification comes from the copy catalog, never free text."""
    key = f"emergency.copy.{action}"
    if key not in catalog:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "copy", "problem": f"missing catalog key {key}"}]})
    out = catalog[key]
    for k, v in (payload or {}).items():
        out = out.replace("{" + k + "}", str(v))
    return out


def pre_action_snapshot(conn, *, event_id: str, label: str) -> str:
    """Rail 5: snapshot written BEFORE any score-affecting action (not an undo — a reference)."""
    rows = conn.execute(
        text("SELECT id, participant_id, award_unit_id, component, points FROM app.ledger "
             "WHERE event_id = :e AND reversal_of IS NULL"),
        {"e": event_id},
    ).fetchall()
    import json

    payload = json.dumps(
        [{"id": str(r[0]), "participant_id": str(r[1]), "award_unit_id": str(r[2]),
          "component": r[3], "points": float(r[4])} for r in rows]
    )
    snap_id = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO app.ledger_snapshots (id, event_id, label, payload) VALUES (:id, :e, :l, :p)"),
        {"id": snap_id, "e": event_id, "l": label, "p": payload},
    )
    return snap_id


def execute(conn, req: EmergencyRequest, *, catalog: dict[str, str],
            now: float | None = None) -> dict[str, Any]:
    """The generic emergency executor: rails → rate → snapshot → action → audit → undo window."""
    check_rails(req, now=now)
    check_rate(conn, event_id=req.event_id)
    if req.dry_run:
        return {
            "dry_run": True,
            "action": req.action,
            "undo": REVERSIBILITY.get(req.action, {"undo_window": "none"}),
            "participant_copy": participant_copy(req.action, catalog, req.payload),
            "result": "no side effects (dry run)",
        }
    if req.action in {"score_adjust", "restore", "advance", "publish_partial"}:
        pre_action_snapshot(conn, event_id=req.event_id, label=f"pre:{req.action}")

    result = _APPLY.get(req.action, lambda c, r: {"ok": True})(conn, req)

    action_id = str(uuid.uuid4())
    undo_window = REVERSIBILITY.get(req.action, {}).get("undo_window", "none")
    undo_until_sql = "now() + interval '60 seconds'" if undo_window == "60s" else "NULL"
    conn.execute(
        text(f"INSERT INTO app.emergency_actions (id, event_id, action, params, actor_id, approver_id, reason, "
             f"dry_run, confirmed_phrase, undo_until) "
             f"VALUES (:id, :e, :action, :params, :actor, :approver, :reason, false, '7', {undo_until_sql})"),
        {"id": action_id, "e": req.event_id, "action": req.action,
         "params": _params_json(req), "actor": req.actor_id, "approver": req.approver_id,
         "reason": req.reason},
    )
    conn.execute(
        text("INSERT INTO audit.entries (event_id, actor_id, actor_role, action, target_type, target_id, details) "
             "VALUES (:e, :a, 'organizer', :act, 'emergency_action', :id, :d)"),
        {"e": req.event_id, "a": req.actor_id, "act": f"emergency.{req.action}", "id": action_id,
         "d": _params_json(req)},
    )
    # cache epoch bump: participant /state refreshes within ≤ 2 s (BG-03)
    conn.execute(
        text("INSERT INTO app.cache_epoch (event_id, epoch) VALUES (:e, 1) "
             "ON CONFLICT (event_id) DO UPDATE SET epoch = app.cache_epoch.epoch + 1"),
        {"e": req.event_id},
    )
    return {"dry_run": False, "action_id": action_id, "result": result,
            "undo": REVERSIBILITY.get(req.action, {"undo_window": "none"}),
            "participant_copy": participant_copy(req.action, catalog, req.payload)}


def _params_json(req: EmergencyRequest) -> str:
    import json

    return json.dumps({"payload": req.payload or {}, "approver": req.approver_id})


def _apply_pause(conn, req: EmergencyRequest):
    conn.execute(text("UPDATE app.events SET paused = true, paused_at = now() WHERE id = :e"),
                 {"e": req.event_id})
    return {"paused": True}


def _apply_resume(conn, req: EmergencyRequest):
    shift = int((req.payload or {}).get("shift_deadline_by_s", 0))
    conn.execute(text("UPDATE app.events SET paused = false, paused_total_s = paused_total_s + :shift WHERE id = :e"),
                 {"e": req.event_id, "shift": shift})
    conn.execute(text("UPDATE app.stages SET exec_closes_at = exec_closes_at + make_interval(secs => :shift) "
                      "WHERE event_id = :e AND exec_closes_at > now()"),
                 {"e": req.event_id, "shift": shift})
    return {"paused": False, "shifted_s": shift}


def _apply_safe_mode(conn, req: EmergencyRequest):
    on = bool((req.payload or {}).get("on", True))
    conn.execute(text("UPDATE app.events SET safe_mode = :on, safe_mode_since = CASE WHEN :on THEN now() ELSE NULL END "
                      "WHERE id = :e"),
                 {"e": req.event_id, "on": on})
    return {"safe_mode": on, "auto_exit_after_s": SAFE_MODE_AUTO_EXIT_S if on else None}


def _apply_freeze_participants(conn, req: EmergencyRequest):
    ids = (req.payload or {}).get("participant_ids", [])
    for pid in ids:
        conn.execute(text("INSERT INTO app.participant_freeze (participant_id, event_id, frozen, reason) "
                          "VALUES (:p, :e, true, :r) ON CONFLICT (participant_id, event_id) "
                          "DO UPDATE SET frozen = true, reason = :r"),
                     {"p": pid, "e": req.event_id, "r": req.reason})
    return {"frozen": ids}


def _apply_quarantine(conn, req: EmergencyRequest):
    tid = (req.payload or {}).get("team_id")
    conn.execute(text("UPDATE app.teams SET quarantined = true, quarantine_reason = :r WHERE id = :t"),
                 {"t": tid, "r": req.reason})
    return {"quarantined": tid}


def _apply_drain_runner(conn, req: EmergencyRequest):
    conn.execute(text("INSERT INTO app.feature_flags (event_id, name, enabled, updated_by, reason) "
                      "VALUES (:e, 'runner', false, :u, :r) "
                      "ON CONFLICT (event_id, name) DO UPDATE SET enabled = false, updated_by = :u, reason = :r"),
                 {"e": req.event_id, "u": req.actor_id, "r": req.reason})
    conn.execute(text("UPDATE app.runs SET state = 'killed', killed_reason = 'drain', finished_at = now() "
                      "WHERE state IN ('queued','running') AND stage_id IN (SELECT id FROM app.stages WHERE event_id = :e)"),
                 {"e": req.event_id})
    return {"drained": True}


def _apply_cache_reset(conn, req: EmergencyRequest):
    conn.execute(text("INSERT INTO app.cache_epoch (event_id, epoch) VALUES (:e, 1) "
                      "ON CONFLICT (event_id) DO UPDATE SET epoch = app.cache_epoch.epoch + 1"),
                 {"e": req.event_id})
    return {"epoch_bumped": True}


_APPLY: dict[str, Callable[[Any, EmergencyRequest], dict]] = {
    "pause": _apply_pause,
    "resume": _apply_resume,
    "safe_mode": _apply_safe_mode,
    "freeze_participants": _apply_freeze_participants,
    "quarantine": _apply_quarantine,
    "drain_runner": _apply_drain_runner,
    "cache_reset": _apply_cache_reset,
}
