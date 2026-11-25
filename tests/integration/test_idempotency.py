"""Idempotency gate (B4): replay returns the original 202 even after the deadline.
Primary coverage: tests/integration/test_submit_locks.py::TestIdempotency (fake DB) and
the CI Postgres job (real unique index). This module asserts the pipeline invariants."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from test_submit_locks import (  # noqa: F401 — collected classes, shared fixture module
    TestDeadlineBoundary,
    TestIdempotency,
    TestLockOrder,
    TestValidation,
    _body,
)
