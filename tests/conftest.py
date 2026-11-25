"""Pytest bootstrap: repo paths on sys.path (backend packages + apps)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (
    str(ROOT / "backend"),
    str(ROOT / "backend" / "apps" / "api_participant"),
    str(ROOT / "backend" / "apps" / "api_admin"),
    str(ROOT / "runner"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import os

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret")
