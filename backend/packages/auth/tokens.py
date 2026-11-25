"""Auth: Argon2id passwords, JWT access tokens, refresh rotation, D-19 supersession.

Corrections applied: R-10/B7 (identifier 5/min + 60 s delay; IP 120/min),
D-19 (single active session with supersession), AUTH-07 (bounded hashing).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from core.errors import ApiError

_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)  # OWASP m=19MiB t=2 p=1


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "password", "problem": "min 12 chars"}]})
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# ---------------------------------------------------------------- JWT (AUTH-03: pin one alg)
def make_access_token(*, secret: str, sub: str, sid: str, role: str, ttl_s: int = 600,
                      alg: str = "HS256", audience: str = "participant") -> str:
    import jwt as pyjwt

    now = int(time.time())
    claims = {
        "iss": "bhctf", "aud": audience, "sub": sub, "sid": sid, "role": role,
        "iat": now, "nbf": now, "exp": now + ttl_s, "jti": secrets.token_hex(8),
    }
    return pyjwt.encode(claims, secret, algorithm=alg)


def decode_access_token(*, secret: str, token: str, audience: str = "participant",
                        alg: str = "HS256") -> dict:
    import jwt as pyjwt

    try:
        return pyjwt.decode(token, secret, algorithms=[alg], audience=audience, issuer="bhctf")
    except pyjwt.ExpiredSignatureError:
        raise ApiError("AUTH_TOKEN_EXPIRED") from None
    except pyjwt.InvalidTokenError:
        raise ApiError("AUTH_FORBIDDEN") from None


# ---------------------------------------------------------------- refresh tokens
def new_refresh_token() -> tuple[str, bytes]:
    """Opaque token; only the hash is stored."""
    token = secrets.token_urlsafe(48)
    return token, hashlib.sha256(token.encode()).digest()


def constant_time_eq(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


# ---------------------------------------------------------------- login rate limits (B7)
@dataclass
class SlidingWindow:
    """Per-identifier sliding window used by the login limiter (DB rows in prod)."""
    limit: int
    window_s: int
    _events: list[float] = field(default_factory=list)

    def hit(self, now: float | None = None) -> bool:
        now = now or time.time()
        self._events = [t for t in self._events if now - t < self.window_s]
        if len(self._events) >= self.limit:
            return False
        self._events.append(now)
        return True

    @property
    def retry_after(self) -> int:
        if not self._events:
            return 0
        oldest = self._events[0]
        return max(0, int(self.window_s - (time.time() - oldest)) + 1)


@dataclass
class LoginLimiter:
    """B7 table:
    - identifier: 5/min sliding; after 5 failures in 10 min add 60 s delay (no hard lockout)
    - IP: 120/min (venue-friendly, NET-01)
    """
    identifier_limit: int = 5
    identifier_window_s: int = 60
    ip_limit: int = 120
    ip_window_s: int = 60
    failure_window_s: int = 600
    failures_for_delay: int = 5
    delay_s: int = 60
    _ident: dict[str, SlidingWindow] = field(default_factory=dict)
    _ip: dict[str, SlidingWindow] = field(default_factory=dict)
    _failures: dict[str, list[float]] = field(default_factory=dict)
    _delayed_until: dict[str, float] = field(default_factory=dict)

    def check(self, *, identifier: str, ip: str, now: float | None = None) -> None:
        now = now or time.time()
        delay_until = self._delayed_until.get(identifier, 0)
        if now < delay_until:
            raise ApiError(
                "AUTH_RATE_LIMITED",
                details={"retry_after": int(delay_until - now) + 1},
            )
        w_ident = self._ident.setdefault(identifier, SlidingWindow(self.identifier_limit, self.identifier_window_s))
        if not w_ident.hit(now):
            raise ApiError("AUTH_RATE_LIMITED", details={"retry_after": w_ident.retry_after})
        w_ip = self._ip.setdefault(ip, SlidingWindow(self.ip_limit, self.ip_window_s))
        if not w_ip.hit(now):
            raise ApiError("AUTH_RATE_LIMITED", details={"retry_after": w_ip.retry_after})

    def record_failure(self, identifier: str, now: float | None = None) -> None:
        now = now or time.time()
        fails = [t for t in self._failures.get(identifier, []) if now - t < self.failure_window_s]
        fails.append(now)
        self._failures[identifier] = fails
        if len(fails) >= self.failures_for_delay:
            self._delayed_until[identifier] = now + self.delay_s
            self._failures[identifier] = []

    def record_success(self, identifier: str) -> None:
        self._failures.pop(identifier, None)
        self._delayed_until.pop(identifier, None)


# ---------------------------------------------------------------- D-19 supersession
def superseded_details(old_session_hint: str | None) -> dict:
    """AUTH_SESSION_SUPERSEDED carries a device hint when permitted (no enumeration)."""
    return {"device_hint": old_session_hint} if old_session_hint else {}
