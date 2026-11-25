#!/usr/bin/env python3
"""Generate openapi/openapi.yaml + openapi/openapi.json from a single source of truth.

A1 Spec Writer artifact (T-1.1, T-1.2). Rules enforced here:
- every operation has request/response schemas and error codes from errors.yaml
- state conflicts are 409; 423 is impossible (R-06)
- /state carries ETag + If-None-Match (R-09/B8)
- uploads never unpack on the API host (R-07/B9)
- runs use allow-listed command_id (R-08/B9)
- participant routes use stage_key (R-18)
- answer-authority + emergency endpoints under /admin (E.1-E.4, 08 Part 4)
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ERRORS = yaml.safe_load((ROOT / "openapi" / "errors.yaml").read_text())["codes"]

def err(*codes: str) -> dict:
    """Build responses entries for the given error codes; code names embedded in the
    description so every endpoint lists every error it can return (T-1.2)."""
    by_http: dict[int, list[str]] = {}
    for code in codes:
        by_http.setdefault(ERRORS[code]["http"], []).append(code)
    return {
        str(http): {
            "description": f"Errors: {', '.join(names)}",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        }
        for http, names in by_http.items()
    }

def ok(desc: str, schema: dict | None = None, status: str = "200") -> dict:
    resp = {"description": desc}
    if schema:
        resp["content"] = {"application/json": {"schema": schema}}
    return {status: resp}

REF = lambda name: {"$ref": f"#/components/schemas/{name}"}

# ---------------------------------------------------------------- components
META_SCHEMA = {
    "type": "object",
    "required": ["request_id", "server_time"],
    "properties": {
        "request_id": {"type": "string", "description": "Correlation id", "example": "req_01J8ZK3M2P"},
        "server_time": {"type": "string", "format": "date-time", "description": "Authoritative server time (UTC)", "example": "2026-12-05T09:41:12.401Z"},
    },
    "additionalProperties": False,
}

def envelope(inner: dict | None) -> dict:
    props = {"meta": REF("Meta")}
    req = ["meta"]
    if inner:
        props["data"] = inner
        req.append("data")
    return {"type": "object", "required": req, "properties": props, "additionalProperties": False}

ERROR_ENVELOPE = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message", "request_id"],
            "properties": {
                "code": {"type": "string", "description": "Stable error code from openapi/errors.yaml"},
                "message": {"type": "string", "description": "Human-readable, safe to display (copy-catalog key resolved)"},
                "details": {"type": "object", "description": "Structured details per error code (e.g. waiting_on[], repo_choice, conflict)"},
                "request_id": {"type": "string"},
            },
            "additionalProperties": False,
        }
    },
    "additionalProperties": False,
}

STAGE_BRIEF = {
    "type": "object",
    "required": ["stage_key", "ordinal", "name", "kind", "state", "submitted"],
    "properties": {
        "stage_key": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$", "description": "Stable slug identity (R-18)", "example": "level_2_flags"},
        "ordinal": {"type": "integer", "description": "Informational order only"},
        "name": {"type": "string"},
        "kind": {"type": "string", "enum": ["explain_only", "flags", "upload"]},
        "explain_opens_at": {"type": "string", "format": "date-time", "nullable": True},
        "exec_opens_at": {"type": "string", "format": "date-time", "nullable": True},
        "exec_closes_at": {"type": "string", "format": "date-time", "nullable": True},
        "state": {"type": "string", "enum": ["locked", "open", "closed"]},
        "paused": {"type": "boolean"},
        "submitted": {"type": "boolean"},
        "gate": {
            "type": "object",
            "properties": {
                "allowed": {"type": "boolean"},
                "waiting_on": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "additionalProperties": False,
}

STATE_SHAPE_V1 = {
    "type": "object",
    "description": "state_shape_v1 (frozen, additive-only; see docs/CONTRACTS.md). ETag = sha256 of version tuple; server_time excluded from the ETag body.",
    "required": ["server_time", "event", "me", "node_pointer", "stages", "team", "versions", "announcements", "feature_flags"],
    "properties": {
        "server_time": {"type": "string", "format": "date-time", "description": "Always fresh; NOT part of the ETag body"},
        "event": {
            "type": "object",
            "required": ["id", "status", "paused", "tz"],
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "status": {"type": "string", "enum": ["draft", "published", "live", "ended", "archived"]},
                "paused": {"type": "boolean"},
                "tz": {"type": "string", "example": "Asia/Kolkata"},
                "maintenance": {"type": "boolean"},
                "safe_mode": {"type": "boolean", "description": "Safe Mode master switch (08 §4.10)"},
            },
        },
        "me": {
            "type": "object",
            "required": ["participant_id", "role", "consent_required"],
            "properties": {
                "participant_id": {"type": "string", "format": "uuid"},
                "team_id": {"type": "string", "format": "uuid", "nullable": True},
                "role": {"type": "string"},
                "consent_required": {"type": "boolean"},
                "min_client_version": {"type": "string", "example": "1.2.0"},
            },
        },
        "node_pointer": {
            "type": "object",
            "required": ["node", "sub_state", "version"],
            "properties": {
                "node": {"type": "string", "enum": ["LANDING", "L1_EXPLAIN", "L1_EXEC", "L1_SUBMITTED", "L2_EXPLAIN", "L2_EXEC", "L2_SUBMITTED", "L3_EXPLAIN", "L3_EXEC", "L3_SUBMITTED", "L4_EXPLAIN", "L4_EXEC", "L4_SUBMITTED", "DONE"]},
                "sub_state": {"type": "string", "enum": ["waiting_repo_lock", "ready", "active", "submitting", "evaluating", "evaluated", "adjusted"], "description": "B11 sub-states"},
                "version": {"type": "integer"},
                "adjusted_by": {"type": "string", "format": "uuid", "nullable": True, "description": "Set when an organizer force-advanced (R-23)"},
            },
        },
        "stages": {"type": "array", "items": REF("StageBrief")},
        "team": {
            "type": "object",
            "required": ["score", "score_version", "repo_choice"],
            "properties": {
                "score": {"type": "number"},
                "score_version": {"type": "integer"},
                "repo_choice": {"type": "string", "nullable": True},
            },
        },
        "versions": {
            "type": "object",
            "required": ["progress_version", "score_version", "leaderboard_version", "flags_version", "announcement_version"],
            "properties": {
                "progress_version": {"type": "integer"},
                "score_version": {"type": "integer"},
                "leaderboard_version": {"type": "integer"},
                "flags_version": {"type": "integer"},
                "announcement_version": {"type": "integer"},
            },
        },
        "announcements": {
            "type": "array",
            "description": "Latest 5; full list via GET /announcements",
            "items": {
                "type": "object",
                "required": ["id", "severity", "body_md", "created_at"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "severity": {"type": "string", "enum": ["info", "warn", "critical"]},
                    "body_md": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
        },
        "feature_flags": {
            "type": "object",
            "required": ["leaderboard", "runner", "ai", "uploads", "announcements", "practice", "read_only"],
            "properties": {
                "leaderboard": {"type": "boolean"}, "runner": {"type": "boolean"},
                "ai": {"type": "boolean"}, "uploads": {"type": "boolean"},
                "announcements": {"type": "boolean"}, "practice": {"type": "boolean"},
                "read_only": {"type": "boolean"},
            },
        },
    },
    "additionalProperties": False,
}

FLAG_INPUT = {
    "type": "object",
    "required": ["file", "lines", "explanation"],
    "properties": {
        "file": {"type": "string", "description": "Path within the team's repo option", "example": "src/auth/session.py"},
        "lines": {"type": "string", "description": "Line range like '41-47' or '41'", "example": "41-47"},
        "explanation": {"type": "string", "maxLength": 2000, "description": "Why this is a defect"},
        "related": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {"file": {"type": "string"}, "lines": {"type": "string"}}}},
        "category": {"type": "string"},
        "runnable_ref": {"type": "string", "description": "Optional reference to scratch files for official runs"},
    },
}

SUBMIT_REQUEST = {
    "description": "Discriminated union by kind (flags for levels 1-2, upload for levels 3-4).",
    "oneOf": [
        {
            "type": "object",
            "required": ["kind", "flags"],
            "properties": {
                "kind": {"type": "string", "enum": ["flags"]},
                "flags": {"type": "array", "minItems": 1, "maxItems": 80, "items": REF("FlagInput")},
            },
        },
        {
            "type": "object",
            "required": ["kind", "upload_id"],
            "properties": {
                "kind": {"type": "string", "enum": ["upload"]},
                "upload_id": {"type": "string", "format": "uuid", "description": "Must have status=ok (or validation=deferred per B9)"},
            },
        },
    ],
}

SUBMIT_202 = {
    "type": "object",
    "required": ["receipt_id", "accepted_at"],
    "properties": {
        "receipt_id": {"type": "string", "description": "Short receipt code (HMAC-derived)", "example": "K7QD-92MX"},
        "accepted_at": {"type": "string", "format": "date-time", "description": "clock_timestamp() captured after the stage-state lock (B6)"},
        "status": {"type": "string", "enum": ["received"]},
    },
}

RUN_REQUEST = {
    "type": "object",
    "required": ["stage_key", "command_id", "workspace"],
    "properties": {
        "stage_key": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$"},
        "command_id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{2,32}$", "description": "Must be in the stage's run_commands allow-list; fixed argv lives server-side (R-08/B9)", "example": "test"},
        "workspace": {
            "description": "Server draft reference, or a small inline delta",
            "oneOf": [
                {"type": "object", "required": ["draft_version"], "properties": {"draft_version": {"type": "integer"}}},
                {"type": "object", "required": ["delta"], "properties": {"delta": {"type": "string", "maxLength": 262144, "description": "≤ 256 KB inline delta"}}},
            ],
        },
        "stdin": {"type": "string", "maxLength": 65536, "description": "Optional base64 stdin"},
        "practice": {"type": "boolean", "default": False, "description": "Practice namespace; hidden inputs unreachable (06 §5)"},
    },
}

RUN_STATE = {
    "type": "object",
    "required": ["id", "state"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "state": {"type": "string", "enum": ["queued", "running", "finished", "timed_out", "killed", "failed"]},
        "stdout_b64": {"type": "string", "description": "Capped; truncated flag set when over MAX_OUTPUT_BYTES"},
        "stderr_b64": {"type": "string"},
        "exit_code": {"type": "integer", "nullable": True},
        "truncated": {"type": "boolean"},
        "queue_position": {"type": "integer", "description": "Present while queued (admission control, 02 §10.5)"},
    },
}

UPLOAD_OBJ = {
    "type": "object",
    "required": ["id", "status"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "status": {"type": "string", "enum": ["stored", "validating", "ok", "failed"], "description": "stored → validating → ok | failed (frozen lifecycle)"},
        "sha256": {"type": "string"},
        "size": {"type": "integer"},
        "problems": {"type": "array", "items": {"type": "string"}, "description": "Present when failed (validation ran on the runner, never the API host)"},
    },
}

DRAFT_PUT = {
    "type": "object",
    "required": ["payload"],
    "properties": {
        "payload": {"type": "object", "description": "Workspace state; ≤ 512 KB serialized (else 413 DRAFT_TOO_LARGE)"},
    },
}

PAGINATION = {
    "name": "cursor",
    "in": "query",
    "required": False,
    "schema": {"type": "string"},
    "description": "Opaque signed cursor",
}

SEC_BEARER = [{"bearerAuth": []}]
SEC_COOKIE = [{"cookieAuth": []}, {"bearerAuth": []}]
SEC_ADMIN = [{"bearerAuth": []}]  # admin audience JWT; Access in front (B10)

COMPONENTS = {
    "securitySchemes": {
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Access token (audience: participant or admin per API)"},
        "cookieAuth": {"type": "apiKey", "in": "cookie", "name": "__Secure-refresh", "description": "HttpOnly refresh cookie, Path=/v1/auth"},
    },
    "schemas": {
        "Meta": META_SCHEMA,
        "ErrorEnvelope": ERROR_ENVELOPE,
        "StageBrief": STAGE_BRIEF,
        "State": STATE_SHAPE_V1,
        "FlagInput": FLAG_INPUT,
        "SubmitRequest": SUBMIT_REQUEST,
        "SubmitAccepted": SUBMIT_202,
        "RunRequest": RUN_REQUEST,
        "RunState": RUN_STATE,
        "Upload": UPLOAD_OBJ,
        "DraftPut": DRAFT_PUT,
    },
}

PATHS: dict = {}

def op(path, method, *, summary, tag, security=None, params=None, body=None, raw_body=None, responses=None, idem=False, desc=None):
    entry = PATHS.setdefault(path, {})
    operation = {
        "summary": summary,
        "description": desc or summary,
        "tags": [tag],
        "operationId": f"{method}_{path}".replace("/", "_").replace("{", "").replace("}", "").replace("-", "_").strip("_"),
        "responses": responses or ok("OK"),
    }
    if security is not None:
        operation["security"] = security
    if params:
        operation["parameters"] = params
    if body:
        operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
    if raw_body:
        operation["requestBody"] = raw_body
    if idem:
        operation.setdefault("parameters", []).append({
            "name": "Idempotency-Key", "in": "header", "required": True,
            "schema": {"type": "string", "minLength": 8, "maxLength": 128},
            "description": "Replay with the same key + payload hash returns the original response, even after the deadline (B4).",
        })
    entry[method] = operation

# ---------------------------------------------------------------- participant API (A3)
op("/v1/auth/login", "post", summary="Sign in", tag="auth",
   body={"type": "object", "required": ["identifier", "password"], "properties": {
       "identifier": {"type": "string", "description": "email or username"},
       "password": {"type": "string", "format": "password"}}},
   responses={**ok("Signed in; sets __Secure-refresh cookie", envelope({"type": "object", "properties": {"access_token": {"type": "string"}, "expires_at": {"type": "string", "format": "date-time"}}}), "200"),
              **err("AUTH_INVALID_CREDENTIALS", "AUTH_RATE_LIMITED", "CLIENT_TOO_OLD", "PAYLOAD_TOO_LARGE", "VALIDATION_ERROR", "INTERNAL")})

op("/v1/auth/refresh", "post", summary="Rotate refresh token", tag="auth", security=SEC_COOKIE,
   responses={**ok("New access token", envelope({"type": "object", "properties": {"access_token": {"type": "string"}}}), "200"),
              **err("AUTH_SESSION_EXPIRED", "AUTH_SESSION_SUPERSEDED", "AUTH_FORBIDDEN", "AUTH_RATE_LIMITED")})

op("/v1/auth/logout", "post", summary="Revoke session", tag="auth", security=SEC_BEARER,
   responses={**ok("Revoked", envelope(None), "200"), **err("AUTH_TOKEN_EXPIRED", "AUTH_SESSION_EXPIRED")})

op("/v1/auth/activate", "post", summary="Activate account via invite", tag="auth", idem=True,
   body={"type": "object", "required": ["token", "password"], "properties": {"token": {"type": "string"}, "password": {"type": "string", "minLength": 12}}},
   responses={**ok("Activated", envelope(None), "200"), **err("NOT_FOUND", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})

op("/v1/auth/reset/request", "post", summary="Request password reset (always generic)", tag="auth", idem=True,
   body={"type": "object", "required": ["email"], "properties": {"email": {"type": "string", "format": "email"}}},
   responses={**ok("Generic confirmation", envelope(None), "200"), **err("AUTH_RATE_LIMITED", "VALIDATION_ERROR")})

op("/v1/auth/reset/confirm", "post", summary="Confirm reset", tag="auth", idem=True,
   body={"type": "object", "required": ["token", "password"], "properties": {"token": {"type": "string"}, "password": {"type": "string", "minLength": 12}}},
   responses={**ok("Password set; sessions revoked", envelope(None), "200"), **err("NOT_FOUND", "VALIDATION_ERROR")})

op("/v1/me", "get", summary="Profile, roles, consent state", tag="auth", security=SEC_BEARER,
   responses={**ok("Profile", envelope({"type": "object"}), "200"), **err("AUTH_TOKEN_EXPIRED", "AUTH_SESSION_EXPIRED", "AUTH_CONSENT_REQUIRED")})

op("/v1/consent", "get", summary="Consent versions and state", tag="consent", security=SEC_BEARER,
   responses={**ok("Consent state", envelope({"type": "object"}), "200"), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/consent", "post", summary="Accept rules/privacy versions", tag="consent", security=SEC_BEARER, idem=True,
   body={"type": "object", "required": ["versions"], "properties": {"versions": {"type": "object"}}},
   responses={**ok("Recorded", envelope(None), "200"), **err("VALIDATION_ERROR", "AUTH_TOKEN_EXPIRED")})

op("/v1/event/public", "get", summary="Public event metadata (cacheable 30s)", tag="public",
   responses=ok("Event metadata", envelope({"type": "object", "properties": {"name": {"type": "string"}, "starts_at": {"type": "string"}, "ends_at": {"type": "string"}, "tz": {"type": "string"}, "brief": {"type": "string"}, "maintenance": {"type": "boolean"}}})))

op("/v1/content/event-details", "get", summary="Sanitized event details markdown", tag="public", responses=ok("Details", envelope({"type": "object", "properties": {"body_md": {"type": "string"}}})))

op("/v1/time", "get", summary="Server time for offset estimation", tag="public",
   responses=ok("Time", envelope({"type": "object", "required": ["server_time"], "properties": {"server_time": {"type": "string", "format": "date-time"}, "tz": {"type": "string"}}})))

op("/v1/state", "get", summary="Authoritative aggregated state (state_shape_v1; ETag from version tuple)", tag="state", security=SEC_BEARER,
   desc="GET /state reads the version tuple, builds the response, ETag = sha256(tuple). If-None-Match matching → 304 with no body. server_time always fresh, excluded from the ETag body (R-09/B8).",
   params=[{"name": "If-None-Match", "in": "header", "required": False, "schema": {"type": "string"}, "description": "ETag from a previous response"}],
   responses={
       "200": {"description": "Full state", "headers": {"ETag": {"schema": {"type": "string"}, "description": "Hash of the version tuple"}}, "content": {"application/json": {"schema": envelope(REF("State"))}}},
       "304": {"description": "Unchanged version tuple"},
       **err("AUTH_TOKEN_EXPIRED", "AUTH_SESSION_EXPIRED", "AUTH_CONSENT_REQUIRED", "CLIENT_TOO_OLD", "UPSTREAM_UNAVAILABLE"),
   })

op("/v1/progress", "get", summary="Node states + deadlines (progress bar)", tag="state", security=SEC_BEARER,
   responses={**ok("Progress", envelope({"type": "object", "properties": {"node_pointer": {"type": "object"}, "stages": {"type": "array", "items": REF("StageBrief")}}})), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/leaderboard", "get", summary="Leaderboard snapshot (mode-aware)", tag="state", security=SEC_BEARER,
   params=[{"name": "since", "in": "query", "required": False, "schema": {"type": "integer"}, "description": "Version; 304 if unchanged"}],
   responses={**ok("Snapshot", envelope({"type": "object"}), "200"), "304": {"description": "Unchanged"}, **err("AUTH_TOKEN_EXPIRED", "MAINTENANCE")})

op("/v1/team", "get", summary="Team members and status", tag="team", security=SEC_BEARER,
   responses={**ok("Team", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/team/score", "get", summary="Team score + version", tag="team", security=SEC_BEARER,
   responses={**ok("Score", envelope({"type": "object", "required": ["score", "version"], "properties": {"score": {"type": "number"}, "version": {"type": "integer"}, "last_updated": {"type": "string", "format": "date-time"}}})), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/announcements", "get", summary="Announcements (paginated)", tag="state", security=SEC_BEARER,
   params=[PAGINATION],
   responses={**ok("Announcements", envelope({"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object"}}, "next_cursor": {"type": "string"}}})), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/repo/tree", "get", summary="Team's repo option tree (watermarked)", tag="repo", security=SEC_BEARER,
   responses={**ok("Tree", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "REPO_ALREADY_LOCKED", "NOT_FOUND")})

op("/v1/repo/files/{path}", "get", summary="Watermarked file content (no-store)", tag="repo", security=SEC_BEARER,
   desc="Cache-Control: private, no-store (R-14). Watermark applied on the fly; line numbers preserved.",
   params=[{"name": "path", "in": "path", "required": True, "schema": {"type": "string"}}],
   responses={**ok("File", envelope({"type": "object", "properties": {"content": {"type": "string"}, "lines": {"type": "integer"}}})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/repo/search", "get", summary="Server-side repo search (20/min)", tag="repo", security=SEC_BEARER,
   params=[{"name": "q", "in": "query", "required": True, "schema": {"type": "string", "maxLength": 200}}, PAGINATION],
   responses={**ok("Results", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "AUTH_RATE_LIMITED")})

op("/v1/team/repo-lock", "get", summary="Current repo choice or null", tag="team", security=SEC_BEARER,
   responses={**ok("Choice", envelope({"type": "object", "properties": {"option": {"type": "string", "nullable": True}}})), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/team/repo-lock", "post", summary="Lock repo choice (lead only, once)", tag="team", security=SEC_BEARER, idem=True,
   body={"type": "object", "required": ["option", "confirm"], "properties": {"option": {"type": "string"}, "confirm": {"type": "boolean", "enum": [True]}}},
   responses={**ok("Locked", envelope({"type": "object"}), "200"), **err("AUTH_FORBIDDEN", "REPO_ALREADY_LOCKED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})

op("/v1/stages/{stage_key}/gate", "get", summary="Gate check (recomputed live, hint ≤ 2 s stale)", tag="stages", security=SEC_BEARER,
   params=[{"name": "stage_key", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$"}}],
   responses={**ok("Gate", envelope({"type": "object", "required": ["allowed"], "properties": {"allowed": {"type": "boolean"}, "reason": {"type": "string"}, "waiting_on": {"type": "array", "items": {"type": "string"}}}})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "GATE_BLOCKED")})

op("/v1/drafts/{stage_key}", "get", summary="Latest server draft", tag="drafts", security=SEC_BEARER,
   params=[{"name": "stage_key", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$"}}],
   responses={**ok("Draft", envelope({"type": "object", "properties": {"version": {"type": "integer"}, "payload": {"type": "object"}, "server_saved_at": {"type": "string", "format": "date-time"}}})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/drafts/{stage_key}", "put", summary="Save draft (If-Match optimistic concurrency; 3-way merge)", tag="drafts", security=SEC_BEARER,
   params=[{"name": "stage_key", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$"}},
           {"name": "If-Match", "in": "header", "required": True, "schema": {"type": "string"}, "description": "Draft version; stale → 409 DRAFT_VERSION_CONFLICT with both versions in details.conflict"}],
   body=REF("DraftPut"),
   responses={**ok("Saved", envelope({"type": "object", "properties": {"version": {"type": "integer"}, "server_saved_at": {"type": "string", "format": "date-time"}}})), **err("AUTH_TOKEN_EXPIRED", "DRAFT_VERSION_CONFLICT", "DRAFT_TOO_LARGE", "STAGE_CLOSED")})

op("/v1/stages/{stage_key}/submit", "post", summary="Submit stage (discriminated flags|upload)", tag="submit", security=SEC_BEARER, idem=True,
   desc="Single transaction: idempotency reserve → stage-state lock → clock_timestamp() once → domain validation → quota lock → submission+flags/artifact+evaluation_event+job+outbox+audit (B6/02 §9.5). 202 with receipt; replay returns original 202 even after deadline.",
   params=[{"name": "stage_key", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[a-z0-9_]{3,32}$"}}],
   body=REF("SubmitRequest"),
   responses={**ok("Accepted", envelope(REF("SubmitAccepted")), "202"),
              **err("AUTH_TOKEN_EXPIRED", "AUTH_CONSENT_REQUIRED", "STAGE_NOT_OPEN", "STAGE_PAUSED", "STAGE_CLOSED", "GATE_BLOCKED", "ALREADY_SUBMITTED", "SUBMISSION_INVALID", "SUBMISSION_CAP_REACHED", "UPLOAD_INVALID", "IDEMPOTENCY_CONFLICT", "RUNNER_UNAVAILABLE", "UPSTREAM_UNAVAILABLE", "PAYLOAD_TOO_LARGE")})

op("/v1/uploads", "post", summary="Upload artifact (stored; validation is a runner job)", tag="uploads", security=SEC_BEARER, idem=True,
   desc="Multipart stream to disk; magic-number check; sha256. NEVER unpacked/parsed/applied on the API host (R-07/B9).",
   raw_body={"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary", "description": ".zip/.diff/.patch ≤ 5 MB"}}}}}},
   responses={**ok("Stored", envelope({"type": "object", "required": ["id", "status"], "properties": {"id": {"type": "string", "format": "uuid"}, "status": {"type": "string", "enum": ["stored"]}}}), "201"),
              **err("AUTH_TOKEN_EXPIRED", "UPLOAD_TOO_LARGE", "UPLOAD_TYPE_UNSUPPORTED", "AUTH_RATE_LIMITED", "IDEMPOTENCY_CONFLICT")})

op("/v1/uploads/{id}/validate", "post", summary="Enqueue upload validation (202 job)", tag="uploads", security=SEC_BEARER, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Job enqueued", envelope({"type": "object", "properties": {"job_id": {"type": "string", "format": "uuid"}}}), "202"), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "IDEMPOTENCY_CONFLICT")})

op("/v1/uploads/{id}", "get", summary="Upload status", tag="uploads", security=SEC_BEARER,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Upload", envelope(REF("Upload"))), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/uploads/{id}", "delete", summary="Delete upload (before submit only)", tag="uploads", security=SEC_BEARER,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Deleted", envelope(None), "200"), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "STAGE_CLOSED")})

op("/v1/runs", "post", summary="Create run (allow-listed command_id; concurrency 1)", tag="runs", security=SEC_BEARER, idem=True,
   desc="command_id must be in the stage's run_commands allow-list. Per-participant concurrency 1; runs/min from config; global admission queue with max depth → RUN_RATE_LIMITED + estimated_wait (B9). Practice namespace separate; hidden inputs never reachable.",
   body=REF("RunRequest"),
   responses={**ok("Run created", envelope(REF("RunState")), "202"),
              **err("AUTH_TOKEN_EXPIRED", "RUN_COMMAND_UNKNOWN", "RUN_RATE_LIMITED", "RUNNER_UNAVAILABLE", "STAGE_NOT_OPEN", "STAGE_CLOSED", "IDEMPOTENCY_CONFLICT", "PAYLOAD_TOO_LARGE")})

op("/v1/runs/{id}", "get", summary="Run state/output", tag="runs", security=SEC_BEARER,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Run", envelope(REF("RunState"))), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/runs/{id}/cancel", "post", summary="Cancel run", tag="runs", security=SEC_BEARER, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Cancelled", envelope(None), "202"), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "IDEMPOTENCY_CONFLICT")})

op("/v1/receipts/{id}", "get", summary="Submission receipt", tag="receipts", security=SEC_BEARER,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
   responses={**ok("Receipt", envelope({"type": "object", "properties": {"status": {"type": "string"}, "counts": {"type": "object"}, "accepted_at": {"type": "string", "format": "date-time"}, "verdict_visibility": {"type": "string"}}})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})

op("/v1/results", "get", summary="Own results (post-finalization only)", tag="receipts", security=SEC_BEARER,
   responses={**ok("Results", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "MAINTENANCE")})

op("/v1/disputes", "post", summary="File a dispute (within appeal window)", tag="receipts", security=SEC_BEARER, idem=True,
   body={"type": "object", "required": ["subject_type", "subject_id", "statement"], "properties": {"subject_type": {"type": "string", "enum": ["award_unit", "submission"]}, "subject_id": {"type": "string", "format": "uuid"}, "statement": {"type": "string", "maxLength": 1000}}},
   responses={**ok("Dispute filed", envelope(None), "202"), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})

op("/v1/disputes", "get", summary="Own disputes", tag="receipts", security=SEC_BEARER, params=[PAGINATION],
   responses={**ok("Disputes", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED")})

op("/v1/config.json", "get", summary="Runtime client config (client version, flags, min version)", tag="public",
   responses=ok("Config", envelope({"type": "object", "properties": {"client_version": {"type": "string"}, "min_client_version": {"type": "string"}, "feature_flags": {"type": "object"}}})))

# practice namespace (PR-04 isolation)
op("/v1/practice/state", "get", summary="Practice state (separate namespace)", tag="practice", security=SEC_BEARER,
   responses={**ok("Practice state", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "MAINTENANCE")})
op("/v1/practice/files/{path}", "get", summary="Practice file content", tag="practice", security=SEC_BEARER,
   params=[{"name": "path", "in": "path", "required": True, "schema": {"type": "string"}}],
   responses={**ok("File", envelope({"type": "object"})), **err("AUTH_TOKEN_EXPIRED", "NOT_FOUND")})
op("/v1/practice/runs", "post", summary="Practice run (sample inputs only; never hidden inputs)", tag="practice", security=SEC_BEARER, idem=True,
   body={"type": "object", "required": ["language", "files"], "properties": {"language": {"type": "string"}, "entrypoint": {"type": "string"}, "files": {"type": "array", "items": {"type": "object"}}, "stdin": {"type": "string"}}},
   responses={**ok("Practice run", envelope(REF("RunState")), "202"), **err("AUTH_TOKEN_EXPIRED", "RUN_RATE_LIMITED", "RUNNER_UNAVAILABLE", "IDEMPOTENCY_CONFLICT")})

# ops endpoints (R-17/B12)
op("/healthz", "get", summary="Liveness", tag="ops", responses=ok("Process up"))
op("/readyz", "get", summary="Readiness (DB, schema head, clock < 100ms, disk)", tag="ops",
   responses={**ok("Ready"), "503": {"description": "Not ready: DB unreachable / schema behind / clock offset > 100 ms / disk over threshold"}})
op("/metrics", "get", summary="Prometheus metrics (internal network only, never Tunnel-routed)", tag="ops", responses=ok("Metrics", {"type": "string"}))

# ---------------------------------------------------------------- admin API (A4)
op("/v1/admin/auth/step-up", "post", summary="Step-up re-auth (valid 5 min)", tag="admin-auth", security=SEC_ADMIN,
   responses={**ok("Stepped up", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_INVALID_CREDENTIALS", "AUTH_STEP_UP_REQUIRED")})
op("/v1/admin/auth/logout", "post", summary="Admin logout", tag="admin-auth", security=SEC_ADMIN,
   responses={**ok("Logged out", envelope(None), "200")})

op("/v1/admin/events", "get", summary="Events list", tag="admin-events", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Events", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/events", "post", summary="Create event", tag="admin-events", security=SEC_ADMIN, idem=True,
   body={"type": "object", "required": ["name", "slug", "tz"], "properties": {"name": {"type": "string"}, "slug": {"type": "string"}, "tz": {"type": "string"}, "capacity": {"type": "integer", "maximum": 50, "description": "Hard cap; N is parametric (R-01/D-25)"}}},
   responses={**ok("Created", envelope({"type": "object"}), "201"), **err("AUTH_FORBIDDEN", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/publish", "post", summary="Publish event (freezes config)", tag="admin-events", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason"], "properties": {"reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Published", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/pause", "post", summary="Pause event (reason required)", tag="admin-live", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason"], "properties": {"reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Paused", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/resume", "post", summary="Resume event", tag="admin-live", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "properties": {"reason": {"type": "string"}, "shift_deadline_by_s": {"type": "integer", "description": "Auto-adjust deadline by paused duration or custom"}}},
   responses={**ok("Resumed", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/stages/{id}/extend", "post", summary="Extend stage", tag="admin-live", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["minutes", "reason"], "properties": {"minutes": {"type": "integer", "minimum": 1}, "reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Extended", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/switches", "get", summary="Kill switches state", tag="admin-live", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Switches", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/events/{id}/switches", "post", summary="Flip a kill switch", tag="admin-live", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["name", "enabled", "reason"], "properties": {"name": {"type": "string", "enum": ["leaderboard", "runner", "ai", "uploads", "announcements", "practice", "read_only", "admission_control"]}, "enabled": {"type": "boolean"}, "reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Switched", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/live", "get", summary="Live console aggregate (no per-participant rows)", tag="admin-live", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Live aggregate", envelope({"type": "object", "description": "Counters per stage, queue age, error rate, runner health, AI health (07 §3.1)"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/events/{id}/announcements", "post", summary="Create announcement", tag="admin-live", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["severity", "body_md"], "properties": {"severity": {"type": "string", "enum": ["info", "warn", "critical", "emergency"]}, "body_md": {"type": "string"}, "audience": {"type": "object"}}},
   responses={**ok("Announced", envelope(None), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/teams/{tid}/advance", "post", summary="Force-advance team (auto-submits pending level first)", tag="admin-live", security=SEC_ADMIN, idem=True,
   desc="Force-advance first runs auto-submit for the pending level using the latest saved draft, then moves the pointer and sets adjusted_by/adjusted_reason (R-23/D.2). Participant sees 'Adjusted by organizer'.",
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}, {"name": "tid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["to_node", "reason"], "properties": {"to_node": {"type": "string"}, "reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Advanced", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/participants/{pid}/state", "get", summary="Read-only participant state (admin preview, no impersonation)", tag="admin-preview", security=SEC_ADMIN,
   desc="E.4: the admin renders participant state in admin-owned components via this endpoint. Tokens, cookies and outbox contents redacted. The participant SPA never runs in the admin origin. Every view is audited.",
   params=[{"name": "pid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Participant state (redacted)", envelope({"type": "object"})), **err("AUTH_FORBIDDEN", "NOT_FOUND")})
op("/v1/admin/preview/effect", "post", summary="Effect preview for a proposed action", tag="admin-preview", security=SEC_ADMIN,
   body={"type": "object", "required": ["action", "payload"], "properties": {"action": {"type": "string"}, "payload": {"type": "object"}}},
   responses={**ok("Effect preview", envelope({"type": "object", "properties": {"participant_copy": {"type": "array", "items": {"type": "string"}}, "scope": {"type": "string"}, "duration": {"type": "string"}, "undo": {"type": "string"}, "render_hint": {"type": "string"}}})), **err("AUTH_FORBIDDEN", "VALIDATION_ERROR")})

# challenges & ground truth
op("/v1/admin/challenges", "get", summary="Challenges list", tag="admin-ch", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Challenges", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/challenges", "post", summary="Create/upload challenge (validated; inert blobs)", tag="admin-ch", security=SEC_ADMIN, idem=True,
   responses={**ok("Created", envelope({"type": "object"}), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "UPLOAD_TOO_LARGE", "UPLOAD_INVALID", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/challenges/{id}/ground-truth", "get", summary="Ground truth (step-up; audited; sensitive banner)", tag="admin-gt", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("GT", envelope({"type": "object"})), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "NOT_FOUND")})
op("/v1/admin/challenges/{id}/ground-truth", "put", summary="Edit GT pre-freeze only (post-freeze → new revision + rescore)", tag="admin-gt", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "properties": {"bugs": {"type": "array", "items": {"type": "object"}}}},
   responses={**ok("Saved", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})

# Answer Authority (E.1-E.3)
op("/v1/admin/challenges/{id}/answer-packs", "get", summary="List answer packs", tag="admin-aa", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Packs", envelope({"type": "object"})), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED")})
op("/v1/admin/challenges/{id}/answer-packs", "post", summary="Create pack from current GT (draft, in gt schema)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Pack created", envelope({"type": "object"}), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/answer-packs/{id}/activate", "post", summary="Activate pack (ground_truth + step-up + two approvers; returns rescore_job_id; NEVER scores inline)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   desc="E.2/E.3: activation starts a rescore job; dry-run deltas must be reviewed first. Requires two distinct approvers and step-up ≤ 5 min.",
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason", "approver_id"], "properties": {"reason": {"type": "string", "minLength": 20}, "approver_id": {"type": "string", "format": "uuid", "description": "Second approver; must differ from actor"}, "announcement_draft_md": {"type": "string", "description": "Must not reveal the new bug's location"}}},
   responses={**ok("Activation → rescore job", envelope({"type": "object", "required": ["rescore_job_id"], "properties": {"rescore_job_id": {"type": "string", "format": "uuid"}}}), "202"),
              **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "ESCALATION_REQUIRED", "AP_OVERLAP_GT", "TIMING_GUARD", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/answer-packs/{id}/entries", "post", summary="Add entry (origin=unplanned; draft; overlap → AP_OVERLAP_GT)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["canonical_file", "line_anchors", "reason"], "properties": {"canonical_file": {"type": "string"}, "line_anchors": {"type": "array", "items": {"type": "object"}}, "aliases": {"type": "array"}, "category": {"type": "string"}, "weight_multiplier": {"type": "number", "default": 1, "description": "R-31 per-bug weight"}, "reason": {"type": "string", "minLength": 20}}},
   responses={**ok("Entry added", envelope({"type": "object"}), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "AP_OVERLAP_GT", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/answer-packs/{id}/entries/{eid}/link", "post", summary="Link a report to an AP entry (writes ledger ap_entry_id)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}, {"name": "eid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["submission_id", "flag_id", "reason"], "properties": {"submission_id": {"type": "string", "format": "uuid"}, "flag_id": {"type": "string", "format": "uuid"}, "reason": {"type": "string", "minLength": 20}}},
   responses={**ok("Linked", envelope(None), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "NOT_FOUND", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/challenges/{id}/candidate-bugs", "get", summary="Candidate bug queue", tag="admin-aa", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Candidates", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/candidate-bugs/{cid}/accept", "post", summary="Accept as draft AP entry (no scoring yet)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   desc="E.2: accepting never scores. It creates a draft AP entry; scoring changes only when the pack is activated (rescore).",
   params=[{"name": "cid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason"], "properties": {"reason": {"type": "string", "minLength": 20}}},
   responses={**ok("Draft entry created", envelope({"type": "object", "properties": {"ap_entry_id": {"type": "string", "format": "uuid"}}}), "201"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/candidate-bugs/{cid}/reject", "post", summary="Reject candidate (reason)", tag="admin-aa", security=SEC_ADMIN, idem=True,
   params=[{"name": "cid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason"], "properties": {"reason": {"type": "string", "minLength": 20}}},
   responses={**ok("Rejected", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})

# rescore & finalize (E.3)
op("/v1/admin/events/{id}/rescore/dry-run", "post", summary="Rescore dry-run (byte-identical to execute; no writes)", tag="admin-rescore", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "properties": {"pack_id": {"type": "string", "format": "uuid"}}},
   responses={**ok("Deltas", envelope({"type": "object", "properties": {"deltas": {"type": "array", "items": {"type": "object"}}, "reversals": {"type": "array", "items": {"type": "object"}}, "affected_participants": {"type": "array", "items": {"type": "string", "format": "uuid"}}}})), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED")})
op("/v1/admin/events/{id}/rescore/execute", "post", summary="Execute rescore (step-up + two approvers + typed RESCORE)", tag="admin-rescore", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["reason", "approver_id", "confirm"], "properties": {"reason": {"type": "string", "minLength": 20}, "approver_id": {"type": "string", "format": "uuid"}, "confirm": {"type": "string", "enum": ["RESCORE"], "description": "Typed confirmation (R-34)"}, "dry_run_id": {"type": "string"}}},
   responses={**ok("Rescore job started", envelope({"type": "object", "properties": {"job_id": {"type": "string", "format": "uuid"}}}), "202"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "ESCALATION_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/leaderboard/mode", "post", summary="Leaderboard mode live|frozen|hidden", tag="admin-rescore", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["mode", "reason"], "properties": {"mode": {"type": "string", "enum": ["live", "frozen", "hidden"]}, "reason": {"type": "string", "minLength": 10}}},
   responses={**ok("Mode set", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/events/{id}/finalize", "post", summary="Finalize (checklist; step-up; irreversible)", tag="admin-rescore", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["confirm"], "properties": {"confirm": {"type": "string", "enum": ["FINALIZE"]}}},
   responses={**ok("Finalized", envelope(None), "200"), **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})

# review & disputes
op("/v1/admin/review/queue", "get", summary="Review queue", tag="admin-review", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Queue", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/review/{id}/claim", "post", summary="Claim (exclusive 15 min)", tag="admin-review", security=SEC_ADMIN,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   responses={**ok("Claimed", envelope(None), "200"), **err("AUTH_FORBIDDEN", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/review/{id}/decide", "post", summary="Decide (reason required; writes ledger)", tag="admin-review", security=SEC_ADMIN, idem=True,
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["decision", "reason"], "properties": {"decision": {"type": "string", "enum": ["accept_full", "accept_partial", "duplicate", "invalid", "unplanned_bug"]}, "reason": {"type": "string", "minLength": 10}, "points": {"type": "number"}, "ai_override": {"type": "boolean"}}},
   responses={**ok("Decided", envelope(None), "200"), **err("AUTH_FORBIDDEN", "IDEMPOTENCY_CONFLICT", "VALIDATION_ERROR")})
op("/v1/admin/disputes", "get", summary="Disputes inbox", tag="admin-review", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Disputes", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})

# emergency (08 Part 4 + 4.12)
op("/v1/admin/events/{id}/emergency/{action}", "post", summary="Emergency action (all rails enforced)", tag="admin-emergency", security=SEC_ADMIN, idem=True,
   desc="All rails (08 §4.12): step-up < 5 min; two distinct approvers for ledger/submission mutations; reason ≥ 20 chars; typed numeral confirmation; dry-run where side effects exist; pre-action snapshot; participant copy from catalog; 60 s auto-revert where reversible; ≤ 10/min per event. Actions: pause, resume, extend, freeze_writes, safe_mode, advance, freeze_participants, kill_sessions, logout_all, quarantine, score_adjust, snapshot, restore, publish_partial, content_push, force_refresh, drain_runner, kill_runs, state_lite, cache_reset.",
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}, {"name": "action", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[a-z_]{3,32}$"}}],
   body={"type": "object", "required": ["reason", "confirm"], "properties": {"reason": {"type": "string", "minLength": 20}, "confirm": {"type": "string", "description": "Typed numeral e.g. '7' (R-34)"}, "approver_id": {"type": "string", "format": "uuid"}, "dry_run": {"type": "boolean", "default": False}, "payload": {"type": "object"}}},
   responses={**ok("Action result (or dry-run preview)", envelope({"type": "object", "properties": {"dry_run": {"type": "boolean"}, "result": {"type": "object"}, "undo": {"type": "object"}}}), "202"),
              **err("AUTH_FORBIDDEN", "AUTH_STEP_UP_REQUIRED", "ESCALATION_REQUIRED", "EMERGENCY_RATE_LIMITED", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/incidents", "post", summary="Declare incident", tag="admin-incidents", security=SEC_ADMIN, idem=True,
   body={"type": "object", "required": ["severity", "summary"], "properties": {"severity": {"type": "string", "enum": ["sev1", "sev2", "sev3"]}, "summary": {"type": "string", "minLength": 20}}},
   responses={**ok("Incident created", envelope({"type": "object"}), "201"), **err("AUTH_FORBIDDEN", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/incidents/{iid}/update", "post", summary="Update incident (timeline)", tag="admin-incidents", security=SEC_ADMIN, idem=True,
   params=[{"name": "iid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["note"], "properties": {"note": {"type": "string"}, "status": {"type": "string"}}},
   responses={**ok("Updated", envelope(None), "200"), **err("AUTH_FORBIDDEN", "NOT_FOUND")})
op("/v1/admin/incidents/{iid}/resolve", "post", summary="Resolve (auto-drafts PIR)", tag="admin-incidents", security=SEC_ADMIN, idem=True,
   params=[{"name": "iid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["resolution"], "properties": {"resolution": {"type": "string", "minLength": 20}}},
   responses={**ok("Resolved; PIR drafted", envelope({"type": "object", "properties": {"pir_id": {"type": "string", "format": "uuid"}}}), "200"), **err("AUTH_FORBIDDEN", "NOT_FOUND")})
op("/v1/admin/incidents/{iid}/assign", "post", summary="Assign incident commander", tag="admin-incidents", security=SEC_ADMIN, idem=True,
   params=[{"name": "iid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["commander_id"], "properties": {"commander_id": {"type": "string", "format": "uuid"}}},
   responses={**ok("Assigned", envelope(None), "200"), **err("AUTH_FORBIDDEN", "NOT_FOUND")})
op("/v1/admin/incidents/{iid}/step", "post", summary="Record runbook step done", tag="admin-incidents", security=SEC_ADMIN, idem=True,
   params=[{"name": "iid", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["runbook_id", "step", "status"], "properties": {"runbook_id": {"type": "string"}, "step": {"type": "integer"}, "status": {"type": "string"}}},
   responses={**ok("Recorded", envelope(None), "200"), **err("AUTH_FORBIDDEN", "NOT_FOUND")})

# users (tenant-scoped, R-36), audit, exports
op("/v1/admin/users", "get", summary="User accounts (tenant-scoped)", tag="admin-system", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Users", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/audit", "get", summary="Audit search (chain verify status included)", tag="admin-system", security=SEC_ADMIN, params=[PAGINATION],
   responses={**ok("Audit", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/audit/verify", "post", summary="Verify audit chain", tag="admin-system", security=SEC_ADMIN,
   responses={**ok("Verification result", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})
op("/v1/admin/exports", "post", summary="Request export (background job; expiring link)", tag="admin-system", security=SEC_ADMIN, idem=True,
   body={"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string"}, "params": {"type": "object"}}},
   responses={**ok("Export queued", envelope({"type": "object"}), "202"), **err("AUTH_FORBIDDEN", "IDEMPOTENCY_CONFLICT")})
op("/v1/admin/health", "get", summary="System health aggregate", tag="admin-system", security=SEC_ADMIN,
   responses={**ok("Health", envelope({"type": "object"})), **err("AUTH_FORBIDDEN")})

# ---------------------------------------------------------------- runner protocol (A7)
op("/runner/claim", "post", summary="Runner pulls a job (mutual TLS / signed per-runner token)", tag="runner",
   security=[{"runnerToken": []}],
   body={"type": "object", "required": ["runner_id", "capacity"], "properties": {"runner_id": {"type": "string"}, "capacity": {"type": "integer"}}},
   responses={**ok("Job spec or 204", {"type": "object", "properties": {"job_id": {"type": "string", "format": "uuid"}, "kind": {"type": "string"}, "image_digest": {"type": "string"}, "argv": {"type": "array", "items": {"type": "string"}}, "env": {"type": "object"}, "limits": {"type": "object"}, "files": {"type": "array", "items": {"type": "object"}, "description": "Short-lived signed URLs from the gateway; runner never receives storage credentials"}, "stdin_ref": {"type": "string"}}}), "204": {"description": "No job available"},
              **err("AUTH_FORBIDDEN", "MAINTENANCE")})
op("/runner/jobs/{id}/heartbeat", "post", summary="Heartbeat (response may cancel)", tag="runner", security=[{"runnerToken": []}],
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["state"], "properties": {"state": {"type": "string"}}},
   responses={**ok("Heartbeat accepted; cancel flag in body", {"type": "object", "properties": {"cancel": {"type": "boolean"}}}), **err("AUTH_FORBIDDEN", "NOT_FOUND")})
op("/runner/jobs/{id}/result", "post", summary="Report result (untrusted; gateway validates schema/size)", tag="runner", security=[{"runnerToken": []}],
   params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
   body={"type": "object", "required": ["state"], "properties": {"state": {"type": "string", "enum": ["finished", "timed_out", "killed", "failed"]}, "exit_code": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}, "usage": {"type": "object"}, "started_at": {"type": "string", "format": "date-time"}, "finished_at": {"type": "string", "format": "date-time"}, "sandbox_fault": {"type": "string"}}},
   responses={**ok("Result accepted", None, "202"), **err("AUTH_FORBIDDEN", "NOT_FOUND", "VALIDATION_ERROR")})

COMPONENTS["securitySchemes"]["runnerToken"] = {"type": "http", "scheme": "bearer", "description": "Signed per-runner token; can only claim and report"}

SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "Bug Hunt CTF API",
        "version": "1.0.0",
        "description": "Frozen contract for participant + admin APIs (state_shape_v1 in docs/CONTRACTS.md). State conflicts are 409 (R-06); no locked status codes are used anywhere.",
    },
    "servers": [{"url": "/"}, {"url": "https://api.example.com/v1", "description": "prod (Tunnel)"}],
    "tags": [{"name": t} for t in ["auth", "consent", "public", "state", "team", "repo", "stages", "drafts", "submit", "uploads", "runs", "receipts", "practice", "ops", "admin-auth", "admin-events", "admin-live", "admin-preview", "admin-ch", "admin-gt", "admin-aa", "admin-rescore", "admin-review", "admin-emergency", "admin-incidents", "admin-system", "runner"]],
    "paths": PATHS,
    "components": COMPONENTS,
}

def main() -> None:
    out = ROOT / "openapi"
    (out / "openapi.yaml").write_text(yaml.safe_dump(SPEC, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    (out / "openapi.json").write_text(json.dumps(SPEC, indent=2), encoding="utf-8")
    n_ops = sum(len([m for m in methods if m in p]) for p in PATHS.values() for methods in [p])
    print(f"openapi: {len(PATHS)} paths, {n_ops} operations -> openapi.yaml + openapi.json")

if __name__ == "__main__":
    main()
