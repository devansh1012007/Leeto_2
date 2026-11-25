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
            if re.search(pat, text, re.I):
                hits.append((f, pat))
    if hits:
        print(f"bundle_check: FAIL — {len(hits)} forbidden pattern(s) in participant build")
        for f, pat in hits[:10]:
            print(f"  {f.name}: /{pat}/")
        return 1
    print("bundle_check: PASS — no admin strings, no gt content, no secrets")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "frontend/apps/participant/dist"))
