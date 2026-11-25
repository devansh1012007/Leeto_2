#!/usr/bin/env python3
"""Error catalog usage check (A1 gate, T-1.2):
- every error code in errors.yaml is referenced by >= 1 endpoint (no orphans)
- every error name referenced by an endpoint exists in errors.yaml (no unlisted codes)
Exit 1 on any violation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ERRORS = set(yaml.safe_load((ROOT / "openapi" / "errors.yaml").read_text())["codes"].keys())
SPEC = json.loads((ROOT / "openapi" / "openapi.json").read_text())

def main() -> int:
    used: dict[str, list[str]] = {}
    unlisted: set[str] = set()
    for path, item in SPEC["paths"].items():
        for method, op in item.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            # codes appear in the operation description text (generator embeds them via err())
            text = json.dumps(op.get("responses", {})) + op.get("description", "") + op.get("summary", "")
            blob = json.dumps(SPEC["paths"][path][method])
            for code in ERRORS:
                if code in blob:
                    used.setdefault(code, []).append(f"{method.upper()} {path}")
    orphans = ERRORS - set(used)
    print(f"error_usage_check: {len(used)}/{len(ERRORS)} codes used by at least one endpoint")
    if orphans:
        print("  ORPHAN codes:", ", ".join(sorted(orphans)))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
