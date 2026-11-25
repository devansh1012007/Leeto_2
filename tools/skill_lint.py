#!/usr/bin/env python3
"""Skill linter (T-0.3 gate): every skills/A*.md has all seven sections."""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = ["## Role", "## Inputs", "## Outputs", "## Hard rules", "## Playbooks", "## Success criteria", "## Handoffs"]
ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    files = sorted((ROOT / "skills").glob("A*.md"))
    errors = []
    if len(files) != 14:
        errors.append(f"expected 14 skill files, found {len(files)}")
    for p in files:
        text = p.read_text()
        for section in REQUIRED:
            if section not in text:
                errors.append(f"{p.name}: missing '{section}'")
    print(f"skill_lint: {len(files)} files checked, {len(errors)} errors")
    for e in errors:
        print("  ERROR:", e)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
