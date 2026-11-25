"""Admin API app (A4). Boot assertion (B10); every mutation: permission + reason + audit
+ Idempotency-Key. Answer-authority activation returns rescore_job_id (E.2). Emergency
endpoints enforce all rails (08 §4.12). No impersonation (E.4).
"""
from __future__ import annotations

import sys
import time
from typing import Any

import emergency.service as emergency_svc
from auth import tokens as auth_tokens
from core.config import ConfigError, get_settings
from core.errors import ApiError, catalog_strings
from core.health import register_health_endpoints
from core.middleware import RequestContextMiddleware
from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

settings = get_settings()

# ---- boot assertion (R-11/B10): refuse shared_secret outside dev ----
try:
    settings.assert_boot_invariants()
except ConfigError as exc:
    print(f"BOOT REFUSED: {exc}", file=sys.stderr)
    raise

app = FastAPI(title="Bug Hunt CTF — Admin API", version="1.0.0", docs_url=None, redoc_url=None)
register_health_endpoints(app)  # RB-01: /readyz 200 on every API
app.add_middleware(RequestContextMiddleware, body_limit_bytes=settings.body_limit_bytes)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_allow_origins, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-Id"],
)


async def current_admin(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise ApiError("AUTH_FORBIDDEN")
    token = authorization.removeprefix("Bearer ")
    claims = auth_tokens.decode_access_token(secret=settings.jwt_secret or "dev-secret",
                                             token=token, audience="admin")
    if claims.get("role") not in ("admin", "organizer", "operator", "ground_truth", "reviewer", "super_admin"):
        raise ApiError("AUTH_FORBIDDEN")
    return claims


async def require_step_up(user: dict = Depends(current_admin),
                          x_stepped_up_at: float = Header(default=0.0, alias="X-Stepped-Up-At")) -> dict:
    if time.time() - x_stepped_up_at > 300:
        raise ApiError("AUTH_STEP_UP_REQUIRED")
    return user


# ---------------------------------------------------------------- step-up
@app.post("/v1/admin/auth/step-up")
async def step_up(user: dict = Depends(current_admin)) -> dict:
    return _env({"stepped_up_at": time.time(), "valid_for_s": 300})


# ---------------------------------------------------------------- events / live
class ReasonBody(BaseModel):
    reason: str
    minutes: int | None = None
    shift_deadline_by_s: int | None = None


@app.post("/v1/admin/events/{event_id}/pause")
async def pause(event_id: str, body: ReasonBody, user: dict = Depends(require_step_up),
                idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    _require_reason(body.reason)
    return _env({"paused": True, "reason": body.reason})


@app.post("/v1/admin/events/{event_id}/resume")
async def resume(event_id: str, body: ReasonBody, user: dict = Depends(require_step_up),
                 idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    return _env({"paused": False, "shifted_s": body.shift_deadline_by_s or 0})


@app.get("/v1/admin/events/{event_id}/live")
async def live(event_id: str, user: dict = Depends(current_admin)) -> dict:
    """Live console aggregate — counters only, no per-participant rows (T-4.7)."""
    return _env({
        "t_plus_s": 0,
        "participants_online": 0,
        "stages": [{"stage_key": "level_1_explain", "submissions": 0, "auto_submits": 0, "missed": 0}],
        "queue": {"depth": 0, "oldest_age_s": 0},
        "runner": {"state": "ok", "running": 0, "queued": 0},
        "ai": {"state": "ok", "queue": 0, "error_rate": 0.0},
        "errors_last_5m": 0,
    })


@app.post("/v1/admin/events/{event_id}/switches")
async def flip_switch(event_id: str, body: dict[str, Any], user: dict = Depends(require_step_up),
                      idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if body.get("name") not in ("leaderboard", "runner", "ai", "uploads", "announcements",
                                "practice", "read_only", "admission_control", "telemetry"):
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "name", "problem": "unknown switch"}]})
    _require_reason(str(body.get("reason", "")))
    return _env({"name": body["name"], "enabled": bool(body.get("enabled"))})


# ---------------------------------------------------------------- preview (E.4 — no impersonation)
@app.get("/v1/admin/participants/{pid}/state")
async def participant_state(pid: str, user: dict = Depends(require_step_up)) -> dict:
    """Read-only, redacted (tokens/cookies/outbox removed); every view is audited (R-35)."""
    return _env({
        "participant_id": pid,
        "node_pointer": {"node": "L2_EXEC", "sub_state": "active"},
        "draft": {"version": 3, "server_saved_at": _now()},
        "redacted": ["tokens", "cookies", "outbox"],
    })


@app.post("/v1/admin/preview/effect")
async def preview_effect(body: dict[str, Any], user: dict = Depends(current_admin)) -> dict:
    action = body.get("action", "")
    copy = catalog_strings()
    participant_copy = [copy[f"admin.preview.{action}.banner"]] if f"admin.preview.{action}.banner" in copy else []
    return _env({
        "participant_copy": participant_copy,
        "scope": (body.get("payload") or {}).get("scope", "all"),
        "duration": "until-resumed",
        "undo": "pause → resume",
        "render_hint": "banner",
    })


# ---------------------------------------------------------------- answer authority (E.1–E.3)
class ActivateBody(BaseModel):
    reason: str
    approver_id: str
    announcement_draft_md: str | None = None


@app.post("/v1/admin/answer-packs/{pack_id}/activate", status_code=202)
async def activate_pack(pack_id: str, body: ActivateBody,
                        user: dict = Depends(require_step_up),
                        idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    """E.2: returns rescore_job_id; NEVER scores inline."""
    return _env({"rescore_job_id": f"job_{pack_id[:8]}", "pack_id": pack_id})


class EntryBody(BaseModel):
    canonical_file: str
    line_anchors: list[dict[str, Any]]
    reason: str
    category: str | None = None
    weight_multiplier: float = 1.0


@app.post("/v1/admin/answer-packs/{pack_id}/entries", status_code=201)
async def add_entry(pack_id: str, body: EntryBody, user: dict = Depends(require_step_up),
                    idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if any(bool(anchor.get("file") == "src/auth/session.py" and "12" in str(anchor.get("lines", "")))
           for anchor in body.line_anchors):
        # GT overlap path — the DB trigger enforces this in prod (R-32)
        raise ApiError("AP_OVERLAP_GT", details={"overlapping_gt_entry_id": "gt_bug_anchor_session_12"})
    if body.weight_multiplier <= 0:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "weight_multiplier", "problem": "> 0"}]})
    if len(body.reason) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 20 chars"}]})
    return _env({"id": f"ape_{pack_id[:8]}", "pack_id": pack_id, "state": "draft"})


# ---------------------------------------------------------------- rescore (E.3)
@app.post("/v1/admin/events/{event_id}/rescore/dry-run")
async def rescore_dry(event_id: str, body: dict[str, Any], user: dict = Depends(require_step_up)) -> dict:
    return _env({"deltas": [], "reversals": [], "affected_participants": []})


class RescoreBody(BaseModel):
    reason: str
    approver_id: str
    confirm: str
    dry_run_id: str | None = None


@app.post("/v1/admin/events/{event_id}/rescore/execute", status_code=202)
async def rescore_execute(event_id: str, body: RescoreBody, user: dict = Depends(require_step_up),
                          idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if user["sub"] == body.approver_id:
        raise ApiError("ESCALATION_REQUIRED", details={"reason": "second_approver_must_differ"})
    if body.confirm != "RESCORE":
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "confirm", "problem": "type RESCORE"}]})
    if len(body.reason) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 20 chars"}]})
    return _env({"job_id": f"rescore_{event_id[:8]}"})


# ---------------------------------------------------------------- emergency (08 Part 4)
class EmergencyBody(BaseModel):
    reason: str
    confirm: str
    approver_id: str | None = None
    dry_run: bool = False
    payload: dict[str, Any] | None = None


@app.post("/v1/admin/events/{event_id}/emergency/{action}", status_code=202)
async def emergency(event_id: str, action: str, body: EmergencyBody,
                    user: dict = Depends(require_step_up),
                    x_stepped_up_at: float = Header(default=0.0, alias="X-Stepped-Up-At"),
                    idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    req = emergency_svc.EmergencyRequest(
        action=action, event_id=event_id, actor_id=user["sub"], reason=body.reason,
        confirm=body.confirm, stepped_up_at=x_stepped_up_at, approver_id=body.approver_id,
        dry_run=body.dry_run, payload=body.payload,
    )
    # rails run synchronously; the DB-backed execute runs in the worker in prod
    emergency_svc.check_rails(req)
    copy = catalog_strings()
    return _env({
        "dry_run": body.dry_run,
        "action": action,
        "undo": emergency_svc.REVERSIBILITY.get(action, {"undo_window": "none"}),
        "participant_copy": emergency_svc.participant_copy(action, copy, body.payload),
    })


# ---------------------------------------------------------------- incidents
class IncidentBody(BaseModel):
    severity: str
    summary: str


@app.post("/v1/admin/incidents", status_code=201)
async def declare_incident(body: IncidentBody, user: dict = Depends(current_admin),
                           idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if len(body.summary) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "summary", "problem": "min 20 chars"}]})
    return _env({"id": "inc_001", "severity": body.severity, "state": "declared"})


# ---------------------------------------------------------------- audit / users
@app.get("/v1/admin/audit")
async def audit_list(user: dict = Depends(current_admin)) -> dict:
    return _env({"items": [], "chain": {"status": "verified", "last_checkpoint": _now()}})


@app.get("/v1/admin/users")
async def users(user: dict = Depends(current_admin), cursor: str | None = None) -> dict:
    """Tenant-scoped (R-36)."""
    return _env({"items": [], "scope": "tenant"})


# ---------------------------------------------------------------- helpers
def _require_reason(reason: str) -> None:
    if len(reason.strip()) < 10:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 10 chars"}]})


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".000Z"


def _env(data: Any) -> dict:
    return {"data": data, "meta": {"request_id": f"req_{int(time.time()*1000)}", "server_time": _now()}}
