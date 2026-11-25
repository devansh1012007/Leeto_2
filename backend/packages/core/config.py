"""Runtime configuration (02 §1.5). Env-var driven; secrets never baked into images."""
from __future__ import annotations

import os
from functools import lru_cache


class ConfigError(RuntimeError):
    pass


class Settings:
    __slots__ = (
        "env", "pg_host", "pg_port", "pg_db", "pg_user", "pg_password",
        "jwt_secret", "jwt_alg", "access_ttl_s", "refresh_ttl_s",
        "admin_auth_mode", "runner_mode", "ai_kind", "storage_kind",
        "storage_path", "body_limit_bytes", "upload_limit_bytes",
        "cors_allow_origins", "clock_max_offset_ms",
    )

    def __init__(self) -> None:
        self.env = os.environ.get("ENV", "dev")
        if self.env not in ("dev", "staging", "prod"):
            raise ConfigError(f"ENV must be dev|staging|prod, got {self.env!r}")
        self.pg_host = os.environ.get("PG_HOST", "localhost")
        self.pg_port = int(os.environ.get("PG_PORT", "5432"))
        self.pg_db = os.environ.get("PG_DB", "bhctf")
        self.pg_user = os.environ.get("PG_USER", "postgres")
        self.pg_password = os.environ.get("PG_PASSWORD", "")
        self.jwt_secret = os.environ.get("JWT_SECRET", "")
        self.jwt_alg = os.environ.get("JWT_ALG", "HS256")
        self.access_ttl_s = int(os.environ.get("ACCESS_TTL_S", "600"))
        self.refresh_ttl_s = int(os.environ.get("REFRESH_TTL_S", str(14 * 24 * 3600)))
        self.admin_auth_mode = os.environ.get("ADMIN_AUTH_MODE", "shared_secret")
        self.runner_mode = os.environ.get("RUNNER_MODE", "stub")
        self.ai_kind = os.environ.get("AI_KIND", "stub")
        self.storage_kind = os.environ.get("STORAGE_KIND", "fs")
        self.storage_path = os.environ.get("STORAGE_PATH", "/var/lib/bhctf/uploads")
        self.body_limit_bytes = int(os.environ.get("BODY_LIMIT_BYTES", str(1024 * 1024)))
        self.upload_limit_bytes = int(os.environ.get("UPLOAD_LIMIT_BYTES", str(5 * 1024 * 1024)))
        self.cors_allow_origins = [
            o for o in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",") if o
        ]
        self.clock_max_offset_ms = int(os.environ.get("CLOCK_MAX_OFFSET_MS", "100"))

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def is_staging_or_prod(self) -> bool:
        return self.env in ("staging", "prod")

    def dsn(self, *, user: str | None = None, password: str | None = None) -> str:
        u = user or self.pg_user
        p = password or self.pg_password
        return f"postgresql+psycopg://{u}:{p}@{self.pg_host}:{self.pg_port}/{self.pg_db}"

    # ---- boot assertions (fail fast; B10, R-02/D.2) ----
    def assert_boot_invariants(self) -> list[str]:
        problems: list[str] = []
        if self.is_staging_or_prod and self.admin_auth_mode == "shared_secret":
            problems.append(
                "ADMIN_AUTH_MODE=shared_secret refuses to start when ENV ∈ {staging, prod} (R-11/B10)"
            )
        if self.is_prod and self.runner_mode == "stub":
            problems.append("RUNNER_MODE=stub refuses to start in ENV=prod (R-02/D.2)")
        if self.is_prod and self.runner_mode not in ("off", "real"):
            problems.append("RUNNER_MODE must be off|real in prod (same-host stub forbidden)")
        if self.is_prod and not self.jwt_secret:
            problems.append("JWT_SECRET is required in prod")
        if self.ai_kind == "remote" and not os.environ.get("PRIVACY_NOTICE_VERSION_BUMPED"):
            problems.append("AI_KIND=remote requires privacy_notice_version bump (DEC-13)")
        if problems:
            raise ConfigError("; ".join(problems))
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    return s
