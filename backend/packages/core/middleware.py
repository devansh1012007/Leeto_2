"""Request pipeline middleware composition (B6 Phase 1 + 02 §13 hygiene).

Order (outermost first): request-id → body-size → rate-limit → auth → authz → validation.
Routes then run Phase 2 (the transaction) inside the handler/service layer.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import ApiError, error_envelope

SENSITIVE_HEADERS = ("authorization", "cookie", "x-runner-token")

# Security headers per 02 §13 (T-3.12).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Cache-Control": "private, no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request-id + body gate + security headers + error envelope + redacted logging."""

    def __init__(self, app, *, body_limit_bytes: int = 1024 * 1024, clock_max_offset_ms: int = 100):
        super().__init__(app)
        self.body_limit = body_limit_bytes
        self.clock_max_offset_ms = clock_max_offset_ms

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id

        # body-size gate (413 early via Content-Length)
        content_length = request.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > self.body_limit:
            return _json_error(ApiError("PAYLOAD_TOO_LARGE"), request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except ApiError as exc:
            response = _json_error(exc, request_id)
        except Exception:  # noqa: BLE001 — unexpected → INTERNAL, never leak internals
            import logging

            logging.getLogger("bhctf.errors").exception("unhandled error on %s", request.url.path)
            response = _json_error(ApiError("INTERNAL"), request_id)

        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers["X-Request-Id"] = request_id

        duration_ms = (time.perf_counter() - start) * 1000
        _log(request, response.status_code, duration_ms)
        return response


def _json_error(exc: ApiError, request_id: str) -> Response:
    import json

    from fastapi.responses import JSONResponse

    body = error_envelope(exc, request_id=request_id)
    resp = JSONResponse(status_code=exc.http, content=json.loads(json.dumps(body, default=str)))
    if exc.code.endswith("RATE_LIMITED"):
        resp.headers["Retry-After"] = str(exc.details.get("retry_after", 5))
    return resp


def _log(request: Request, status: int, duration_ms: float) -> None:
    """Structured logging with an allow-list; NEVER tokens/passwords/report text (SEC-06)."""
    import logging

    logging.getLogger("bhctf.access").info(
        "request",
        extra={
            "route": request.url.path,
            "method": request.method,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "request_id": getattr(request.state, "request_id", "-"),
        },
    )
