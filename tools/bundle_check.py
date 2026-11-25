#!/usr/bin/env python3
"""T-5.11 / CI bundle-check: the participant build must contain ZERO admin strings,
zero ground-truth content, zero secret patterns. Exit 1 on any hit."""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = [
    r"answer.?authority",
    r"emergency control room",
    r"/v1/admin/",
    r"ground.?truth",
    r"AP_OVERLAP_GT",
    r"rescore_job_id",
    r"ADMIN_ACCESS_SHARED_SECRET",
    r"X-Runner-Token",
    r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]

def main(dist: str) -> int:
    hits: list[tuple[Path, str]] = []
    for f in Path(dist).rglob("*"):
        if not f.is_file():
            continue
        text = f.read_text(errors="ignore")
        for pat in FORBIDDEN:
            if re.search(pat, text, re.IGNORECASE):
                hits.append((f, pat))
    if hits:
        print(f"bundle_check: FAIL — {len(hits)} forbidden pattern(s) in participant build")
        for f, pat in hits[:10]:
            print(f"  {f.name}: /{pat}/")
        return 1
    print("bundle_check: PASS — no admin strings, no gt content, no secrets")
    return 0

def view_as_check(admin_src: str = "frontend/apps/admin/src") -> int:
    """R-28/E.4: no impersonation route anywhere. Checks Route paths and Links, not comments."""
    hits = []
    for f in Path(admin_src).rglob("*.tsx"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if ('path="/view-as' in line or 'to="/view-as' in line or "viewAs" in line):
                hits.append(f"{f}:{i}")
    if hits:
        print("view_as_check: FAIL —", hits[:5])
        return 1
    print("view_as_check: PASS — no impersonation route (R-28/E.4)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "view-as":
        sys.exit(view_as_check(sys.argv[2] if len(sys.argv) > 2 else "frontend/apps/admin/src"))
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "frontend/apps/participant/dist"))
