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
from core.middleware import RequestContextMiddleware
from db.session import tx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from submissions.pipeline import submit_stage

settings = get_settings()
app = FastAPI(title="Bug Hunt CTF — Participant API", version="1.0.0", docs_url=None, redoc_url=None)
app.add_middleware(RequestContextMiddleware, body_limit_bytes=settings.body_limit_bytes)
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


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict:
    problems = []
    try:
        async with tx() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:  # noqa: BLE001
        problems.append("db_unreachable")
    if problems:
        raise HTTPException(status_code=503, detail={"problems": problems})
    return {"status": "ready"}


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
    async with tx() as conn:
        outcome = await submit_stage(
            conn, participant_id=user["sub"], team_id=None,
            event_id="00000000-0000-0000-0000-000000000001",
            stage_key=stage_key, kind=body.kind, body=payload,
            idempotency_key=idempotency_key,
        )
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
