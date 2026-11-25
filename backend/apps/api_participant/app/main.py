"""Participant API app (A3). Endpoints per openapi/openapi.yaml; every response carries
server_time; /state is version-keyed with ETag (R-09/B8); uploads never unpack (R-07).
"""
from __future__ import annotations

import json
import time
from typing import Any

import ai.assessor as ai_mod
import runner.gateway as runner_mod
from auth import tokens as auth_tokens
from core.config import get_settings
from core.errors import ApiError
from core.health import register_health_endpoints
from core.middleware import RequestContextMiddleware
from db.session import tx

# payload_hash reserved for idempotency body hashing on the DB path
from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from submissions.pipeline import submit_stage

settings = get_settings()
app = FastAPI(title="Bug Hunt CTF — Participant API", version="1.0.0", docs_url=None, redoc_url=None)
app.add_middleware(RequestContextMiddleware, body_limit_bytes=settings.body_limit_bytes)
register_health_endpoints(app)  # /healthz + /readyz + /metrics (RB-01)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,   # exact allow-list (NET-05)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Version", "Idempotency-Key", "If-Match", "If-None-Match", "X-Request-Id"],
)

# process-level services (dev/staging: in-process; prod wiring via compose)
login_limiter = auth_tokens.LoginLimiter()
runner_gateway = runner_mod.RunnerGateway()
assessor = ai_mod.StubAssessor(env=settings.env)


# ---------------------------------------------------------------- auth dependency
async def current_user(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise ApiError("AUTH_FORBIDDEN")
    token = authorization.removeprefix("Bearer ")
    try:
        claims = auth_tokens.decode_access_token(secret=settings.jwt_secret or "dev-secret", token=token)
    except ApiError:
        raise
    request.state.participant_id = claims["sub"]
    return claims


def require_body_version(x_client_version: str = Header(default="1.0.0")) -> None:
    min_v = "0.1.0"
    if _ver_lt(x_client_version, min_v):
        raise ApiError("CLIENT_TOO_OLD")


def _ver_lt(a: str, b: str) -> bool:
    def key(v: str):
        return tuple(int(x) for x in v.split("."))
    return key(a) < key(b)


# ---------------------------------------------------------------- public + ops
@app.get("/v1/event/public")
async def public_event() -> dict:
    return _env({"name": "Bug Hunt CTF", "tz": "Asia/Kolkata", "maintenance": False})


@app.get("/v1/time")
async def server_time() -> dict:
    return _env({"server_time": _now(), "tz": "Asia/Kolkata"})


@app.get("/v1/config.json")
async def client_config() -> dict:
    return _env({"client_version": "1.0.0", "min_client_version": "0.1.0",
                 "feature_flags": {"runner": settings.runner_mode != "off", "ai": settings.ai_kind != "off"}})


# ---------------------------------------------------------------- auth routes
class LoginBody(BaseModel):
    identifier: str
    password: str


@app.post("/v1/auth/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    ip = request.client.host if request.client else "unknown"
    login_limiter.check(identifier=body.identifier, ip=ip)
    login_limiter.record_failure(body.identifier)   # deterministic stub auth: always one failure path shape
    raise ApiError("AUTH_INVALID_CREDENTIALS")


@app.post("/v1/auth/logout")
async def logout(user: dict = Depends(current_user)) -> dict:
    return _env({"revoked": True})


@app.get("/v1/me")
async def me(user: dict = Depends(current_user)) -> dict:
    return _env({"participant_id": user["sub"], "role": user.get("role", "participant"),
                 "consent_required": False})


# ---------------------------------------------------------------- /state (R-09/B8)
@app.get("/v1/state")
async def state(request: Request, response: Response,
                user: dict = Depends(current_user),
                if_none_match: str | None = Header(default=None, alias="If-None-Match")) -> Any:
    participant_id = user["sub"]
    # version-keyed: a worker with a stale key can never serve a stale pointer
    versions = _versions_for(participant_id)
    etag = _state_etag(versions)
    if if_none_match == etag:
        response.status_code = 304
        return None
    response.headers["ETag"] = etag
    body = {
        "event": {"id": "00000000-0000-0000-0000-000000000001", "status": "live",
                  "paused": False, "tz": "Asia/Kolkata", "maintenance": False, "safe_mode": False},
        "me": {"participant_id": participant_id, "team_id": None, "role": "participant",
               "consent_required": False, "min_client_version": "0.1.0"},
        "node_pointer": {"node": "L1_EXPLAIN", "sub_state": "ready", "version": 1, "adjusted_by": None},
        "stages": [{
            "stage_key": "level_1_explain", "ordinal": 1, "name": "Level 1 — Read the code",
            "kind": "explain_only", "state": "open", "submitted": False,
            "gate": {"allowed": True, "waiting_on": []},
        }],
        "team": {"score": 0, "score_version": 0, "repo_choice": None},
        "versions": versions,
        "announcements": [],
        "feature_flags": {"leaderboard": True, "runner": True, "ai": True, "uploads": True,
                          "announcements": True, "practice": True, "read_only": False},
    }
    return _env(body)


@app.get("/v1/progress")
async def progress(user: dict = Depends(current_user)) -> dict:
    return _env({"node_pointer": {"node": "L1_EXPLAIN", "sub_state": "ready", "version": 1},
                 "stages": []})


# ---------------------------------------------------------------- drafts
class DraftBody(BaseModel):
    payload: dict[str, Any]


@app.put("/v1/drafts/{stage_key}")
async def put_draft(stage_key: str, body: DraftBody, user: dict = Depends(current_user),
                    if_match: str = Header(alias="If-Match")) -> dict:
    if len(json.dumps(body.payload)) > 512 * 1024:
        raise ApiError("DRAFT_TOO_LARGE")
    if not if_match.isdigit():
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "If-Match", "problem": "version int"}]})
    # optimistic concurrency: stale version → conflict with both versions (T-5.5)
    if int(if_match) < 1:
        raise ApiError("DRAFT_VERSION_CONFLICT", details={
            "conflict": {"server_version": 2, "client_version": int(if_match)}})
    return _env({"version": int(if_match) + 1, "server_saved_at": _now()})


# ---------------------------------------------------------------- submit (B6)
class SubmitFlags(BaseModel):
    file: str
    lines: str
    explanation: str
    category: str | None = None


class SubmitBody(BaseModel):
    kind: str
    flags: list[SubmitFlags] | None = None
    upload_id: str | None = None


@app.post("/v1/stages/{stage_key}/submit", status_code=202)
async def submit(stage_key: str, body: SubmitBody, user: dict = Depends(current_user),
                 idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    payload = {"kind": body.kind,
               "flags": [f.model_dump() for f in (body.flags or [])],
               "upload_id": body.upload_id}
    try:
        async with tx() as conn:
            outcome = await submit_stage(
                conn, participant_id=user["sub"], team_id=None,
                event_id="00000000-0000-0000-0000-000000000001",
                stage_key=stage_key, kind=body.kind, body=payload,
                idempotency_key=idempotency_key,
            )
    except ApiError:
        raise
    except Exception:  # noqa: BLE001 — DB unreachable: 503 UPSTREAM_UNAVAILABLE, never 500 (02 §12)
        raise ApiError("UPSTREAM_UNAVAILABLE") from None
    return _env({"receipt_id": outcome.receipt_id, "accepted_at": outcome.accepted_at,
                 "status": "received", "replay": outcome.replay})


# ---------------------------------------------------------------- runs (B9)
class RunBody(BaseModel):
    stage_key: str
    command_id: str
    workspace: dict[str, Any]
    stdin: str | None = None
    practice: bool = False


ALLOWED_COMMANDS = {"build", "test", "lint"}  # stage config table in prod; allow-list only (B9/R-08)


@app.post("/v1/runs", status_code=202)
async def create_run(body: RunBody, user: dict = Depends(current_user),
                     idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if body.command_id not in ALLOWED_COMMANDS:
        raise ApiError("RUN_COMMAND_UNKNOWN")
    job_id = runner_gateway.submit(
        participant_id=user["sub"], team_id=None,
        kind="run_practice" if body.practice else "run_official",
        command_argv=[f"/usr/bin/{body.command_id}"],
        image_digest="sha256:stub-python-3.12",
    )
    return _env({"id": job_id, "state": "queued"})


@app.get("/v1/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(current_user)) -> dict:
    result = runner_gateway.get_result(run_id)
    if result is None:
        raise ApiError("NOT_FOUND")
    return _env({"id": run_id, "state": result.get("state", "queued"), "exit_code": result.get("exit_code"),
                 "stdout_b64": result.get("stdout", ""), "stderr_b64": result.get("stderr", ""),
                 "truncated": False})


# ---------------------------------------------------------------- uploads (R-07/B9)
@app.post("/v1/uploads", status_code=201)
async def create_upload(user: dict = Depends(current_user),
                        idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    return _env({"id": "00000000-0000-0000-0000-000000000002", "status": "stored"})


@app.post("/v1/uploads/{upload_id}/validate", status_code=202)
async def validate_upload(upload_id: str, user: dict = Depends(current_user),
                          idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    # validation runs on the RUNNER as an async job — never unpacked here (R-07)
    return _env({"job_id": "00000000-0000-0000-0000-000000000003"})


@app.get("/v1/uploads/{upload_id}")
async def upload_status(upload_id: str, user: dict = Depends(current_user)) -> dict:
    return _env({"id": upload_id, "status": "ok"})


@app.delete("/v1/uploads/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(current_user)) -> dict:
    # owner check on the DB path (IDOR matrix); stub mode is single-tenant
    return _env({"id": upload_id, "deleted": True})


# ---------------------------------------------------------------- auth lifecycle
@app.post("/v1/auth/refresh")
async def refresh() -> dict:
    # deterministic stub: no session store without DB → session expired (fail closed).
    # DB path: rotate app.sessions refresh token with supersession (D-19).
    raise ApiError("AUTH_SESSION_EXPIRED")


class ActivateBody(BaseModel):
    token: str
    password: str


@app.post("/v1/auth/activate")
async def activate(body: ActivateBody,
                   idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if len(body.password) < 12:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "password", "problem": "minLength 12"}]})
    # DB path: app.activation_tokens lookup; stub mode has no pending invitations.
    raise ApiError("NOT_FOUND")


class ResetRequestBody(BaseModel):
    email: str


@app.post("/v1/auth/reset/request")
async def reset_request(body: ResetRequestBody,
                        idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    # never reveal whether the address exists (no user enumeration)
    return _env({"accepted": True})


class ResetConfirmBody(BaseModel):
    token: str
    password: str


@app.post("/v1/auth/reset/confirm")
async def reset_confirm(body: ResetConfirmBody,
                        idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if len(body.password) < 12:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "password", "problem": "minLength 12"}]})
    raise ApiError("NOT_FOUND")


# ---------------------------------------------------------------- consent
@app.get("/v1/consent")
async def get_consent(user: dict = Depends(current_user)) -> dict:
    return _env({"required": False, "versions": {"rules": "2026-11-01", "privacy": "2026-11-01"},
                 "accepted": True})


@app.post("/v1/consent")
async def post_consent(body: dict[str, Any], user: dict = Depends(current_user),
                       idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if not isinstance(body.get("versions"), dict) or not body["versions"]:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "versions", "problem": "object required"}]})
    return _env({"accepted": True, "versions": body["versions"]})


# ---------------------------------------------------------------- content
@app.get("/v1/content/event-details")
async def event_details() -> dict:
    # public static content; served from content/ (publish flow writes it)
    return _env({"sections": [
        {"id": "format", "title": "Format",
         "body": "4 levels — read (L1), flag bugs (L2), fix + hidden tests (L3), tests + docs (L4)."},
        {"id": "schedule", "title": "Schedule",
         "body": "Published on the lobby page; all times in IST (Asia/Kolkata)."},
        {"id": "teams", "title": "Teams",
         "body": "Team size 2 (one lead); repo choice is a one-time team decision."},
    ]})


# ---------------------------------------------------------------- announcements
@app.get("/v1/announcements")
async def announcements(cursor: str | None = None, user: dict = Depends(current_user)) -> dict:
    # DB path: app.announcements keyed by announcement_version; stub: none pending
    return _env({"items": [], "next_cursor": None})


# ---------------------------------------------------------------- leaderboard
@app.get("/v1/leaderboard")
async def leaderboard(since: int | None = None, user: dict = Depends(current_user)) -> Any:
    versions = _versions_for(user["sub"])
    current = versions["leaderboard_version"]
    if since is not None and since == current:
        return Response(status_code=304)
    # DB path: latest app.leaderboard_snapshots row for the event (JOB-08 debounced).
    return _env({"version": current, "frozen": False, "mode": "live",
                 "entries": [], "updated_at": _now()})


# ---------------------------------------------------------------- receipts / results
@app.get("/v1/receipts/{receipt_id}")
async def receipt(receipt_id: str, user: dict = Depends(current_user)) -> dict:
    return _env({"id": receipt_id, "status": "received", "submitted_at": _now(),
                 "stage_key": "level_2_flags", "replay": False})


@app.get("/v1/results")
async def results(user: dict = Depends(current_user)) -> dict:
    # final results exist only after admin finalize; stub event is live → 404
    raise ApiError("NOT_FOUND")


# ---------------------------------------------------------------- disputes
@app.post("/v1/disputes", status_code=202)
async def file_dispute(body: dict[str, Any], user: dict = Depends(current_user),
                       idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    subject_type = body.get("subject_type")
    if subject_type not in ("award_unit", "deduction", "receipt"):
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "subject_type", "problem": "award_unit|deduction|receipt"}]})
    if not isinstance(body.get("subject_id"), str) or not body["subject_id"]:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "subject_id", "problem": "string required"}]})
    if not isinstance(body.get("statement"), str) or len(body["statement"]) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "statement", "problem": "min 20 chars"}]})
    return _env({"dispute_id": "00000000-0000-0000-0000-000000000010",
                 "status": "open", "filed_at": _now()})


@app.get("/v1/disputes")
async def list_disputes(cursor: str | None = None, user: dict = Depends(current_user)) -> dict:
    return _env({"items": [], "next_cursor": None})


# ---------------------------------------------------------------- team
@app.get("/v1/team")
async def team(user: dict = Depends(current_user)) -> dict:
    # DB path: app.teams join members; stub participant has no team yet → 404
    raise ApiError("NOT_FOUND")


@app.get("/v1/team/score")
async def team_score(user: dict = Depends(current_user)) -> dict:
    versions = _versions_for(user["sub"])
    return _env({"score": 0, "score_version": versions["score_version"],
                 "breakdown": []})


@app.get("/v1/team/repo-lock")
async def repo_lock_get(user: dict = Depends(current_user)) -> dict:
    return _env({"locked": False, "option": None, "locked_at": None})


@app.post("/v1/team/repo-lock")
async def repo_lock_set(body: dict[str, Any], user: dict = Depends(current_user),
                        idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if body.get("confirm") is not True:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "confirm", "problem": "must be true"}]})
    option = body.get("option")
    if option not in ("option_a", "option_b"):
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "option", "problem": "unknown repo option"}]})
    # team-lead-only on the DB path (AUTH_FORBIDDEN); already-locked → REPO_ALREADY_LOCKED
    return _env({"locked": True, "option": option, "locked_at": _now()})


# ---------------------------------------------------------------- stage gate + drafts
@app.get("/v1/stages/{stage_key}/gate")
async def stage_gate(stage_key: str, user: dict = Depends(current_user)) -> dict:
    if not stage_key.startswith("level_"):
        raise ApiError("NOT_FOUND")
    return _env({"stage_key": stage_key, "allowed": True, "waiting_on": []})


@app.get("/v1/drafts/{stage_key}")
async def get_draft(stage_key: str, user: dict = Depends(current_user)) -> dict:
    return _env({"stage_key": stage_key, "version": 1, "payload": {},
                 "server_saved_at": _now()})


# ---------------------------------------------------------------- runs: cancel
@app.post("/v1/runs/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: str, user: dict = Depends(current_user),
                     idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    if runner_gateway.get_result(run_id) is None and not run_id.startswith("run_"):
        raise ApiError("NOT_FOUND")
    runner_gateway.cancel(run_id)
    return _env({"id": run_id, "state": "cancelling"})


# ---------------------------------------------------------------- repo browser (WS-02/03)
_REPO_FILES: dict[str, str] = {
    "src/auth/session.py": (
        "import hmac\n\n"
        "def verify_session(provided: str, expected: str) -> bool:\n"
        "    # BUG (planted): non-constant-time compare leaks the expected token\n"
        "    return provided == expected\n"
    ),
    "src/checkout/total.py": (
        "def total(items):\n"
        "    # BUG (planted): float cents math loses precision\n"
        "    return sum(i.price for i in items) * 100\n"
    ),
    "src/README.md": "# Challenge repo (option_a) — Web checkout service (Python)\n",
}


@app.get("/v1/repo/tree")
async def repo_tree(user: dict = Depends(current_user)) -> dict:
    # DB path: challenge version pinned to the team's repo_choice
    return _env({"files": sorted(_REPO_FILES), "version": 1})


@app.get("/v1/repo/files/{file_path:path}")
async def repo_file(file_path: str, user: dict = Depends(current_user)) -> dict:
    content = _REPO_FILES.get(file_path)
    if content is None:
        raise ApiError("NOT_FOUND")
    return _env({"path": file_path, "content": content, "size": len(content)})


@app.get("/v1/repo/search")
async def repo_search(q: str, cursor: str | None = None,
                      user: dict = Depends(current_user)) -> dict:
    if not q or len(q) < 2:
        raise ApiError("VALIDATION_ERROR", details={"fields": [
            {"field": "q", "problem": "min 2 chars"}]})
    hits = [{"path": p, "line": 1, "snippet": line.strip()}
            for p, c in sorted(_REPO_FILES.items())
            for line in c.splitlines() if q.lower() in line.lower()]
    return _env({"hits": hits[:20], "next_cursor": None})


# ---------------------------------------------------------------- practice (R-02)
@app.get("/v1/practice/state")
async def practice_state(user: dict = Depends(current_user)) -> dict:
    return _env({"enabled": True, "remaining_runs": 10, "cooldown_s": 60,
                 "commands": ["build", "test", "lint"]})


@app.get("/v1/practice/files/{file_path:path}")
async def practice_file(file_path: str, user: dict = Depends(current_user)) -> dict:
    content = _REPO_FILES.get(file_path)
    if content is None:
        raise ApiError("NOT_FOUND")
    return _env({"path": file_path, "content": content})


class PracticeRunBody(BaseModel):
    language: str
    files: dict[str, Any]
    entrypoint: str | None = None


@app.post("/v1/practice/runs", status_code=202)
async def practice_run(body: PracticeRunBody, user: dict = Depends(current_user),
                       idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    # practice runs execute ONLY runner-side on the practice image; hidden inputs are
    # unreachable by construction (separate volume, no gt mount) — R-02/DV-02.
    job_id = runner_gateway.submit(
        participant_id=user["sub"], team_id=None, kind="run_practice",
        command_argv=["/usr/bin/practice"],
        image_digest="sha256:stub-practice-3.12",
    )
    return _env({"id": job_id, "state": "queued"})


# ---------------------------------------------------------------- helpers
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".000Z"


def _env(data: Any) -> dict:
    return {"data": data, "meta": {"request_id": f"req_{int(time.time()*1000)}", "server_time": _now()}}


def _versions_for(participant_id: str) -> dict:
    return {"progress_version": 1, "score_version": 0, "leaderboard_version": 0,
            "flags_version": 1, "announcement_version": 1}


def _state_etag(versions: dict) -> str:
    blob = json.dumps(versions, sort_keys=True)
    import hashlib

    return f'"{hashlib.sha256(blob.encode()).hexdigest()[:24]}"'
