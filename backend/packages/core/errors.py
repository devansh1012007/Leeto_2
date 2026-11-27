"""Canonical error catalog + envelope (A3/A4 shared).

Single source: openapi/errors.yaml. This module loads it at import time so the
runtime and the contract can never drift (R-06/B3).
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

# In a Docker image the installed packages live in site-packages, so the
# default walk-up lands in /usr/local/lib. The build sets BHCTF_REPO_ROOT to
# the image root (where openapi/ and copy/ are copied); in a source checkout
# the walk-up reaches the repo root.
REPO_ROOT = Path(os.environ.get("BHCTF_REPO_ROOT") or Path(__file__).resolve().parents[3])
ERRORS: dict[str, dict] = yaml.safe_load((REPO_ROOT / "openapi" / "errors.yaml").read_text())["codes"]


class ApiError(Exception):
    """Raised by services; converted to the frozen error envelope by middleware."""

    def __init__(self, code: str, *, details: dict[str, Any] | None = None, message: str | None = None):
        if code not in ERRORS:
            raise ValueError(f"unlisted error code: {code} (add to openapi/errors.yaml first)")
        super().__init__(message or ERRORS[code]["description"])
        self.code = code
        self.http = ERRORS[code]["http"]
        self.details = details or {}
        self.message = message or ERRORS[code]["description"]


def envelope(data: Any, *, request_id: str, server_time: str) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": request_id, "server_time": server_time}}


def error_envelope(exc: ApiError, *, request_id: str) -> dict[str, Any]:
    err: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
        "request_id": request_id,
    }
    if exc.details:
        err["details"] = exc.details
    return {"error": err}


@functools.lru_cache(maxsize=1)
def catalog_strings() -> dict[str, str]:
    """copy/catalog.yaml strings for error.<code> keys."""
    data = yaml.safe_load((REPO_ROOT / "copy" / "catalog.yaml").read_text())
    return data["strings"]


def display_message(exc: ApiError) -> str:
    """Resolve the participant-facing message from the copy catalog (never free text)."""
    strings = catalog_strings()
    return strings.get(f"error.{exc.code}", exc.message)
