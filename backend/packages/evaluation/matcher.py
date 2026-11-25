"""Deterministic matcher + evaluation pipeline (02 §9.1–§9.3, corrections R-04/E.2).

Matcher rules:
1. Candidate bugs: same canonical file (or alias).
2. Line match: containment with ±2 line tolerance; span > 200 lines → structural reject.
3. Multi-location flags: ≥ ceil(0.5 × locations) matched anchors.
4. Category agreement raises confidence, never decides alone.
5. Deterministic: same inputs → same outputs; matcher_version + rule_set_hash recorded.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

MATCHER_VERSION = "1.0.0"


def rule_set_hash() -> str:
    return hashlib.sha256(MATCHER_VERSION.encode()).hexdigest()[:16]


@dataclass
class Bug:
    award_unit_id: str
    canonical_file: str
    line_anchors: list[dict]          # [{file, lines: "12-16"}]
    aliases: list[dict] = field(default_factory=list)
    category: str | None = None
    root_cause_group: str | None = None
    severity: str | None = None


@dataclass
class Flag:
    file: str
    lines: str                        # "41-47"
    explanation: str = ""
    related: list[dict] = field(default_factory=list)


def _parse_lines(spec: str) -> tuple[int, int]:
    start, _, end = spec.partition("-")
    try:
        s, e = int(start), int(end or start)
    except ValueError:
        return 0, 0
    return s, e


def _overlap(a: tuple[int, int], b: tuple[int, int], tolerance: int = 2) -> bool:
    return a[0] <= b[1] + tolerance and b[0] <= a[1] + tolerance


@dataclass
class MatchResult:
    award_unit_id: str | None
    confidence: float
    outcome: str                      # auto_accept | needs_review | structural_reject | no_candidate
    evidence: dict[str, Any]


def match_flag(flag: Flag, bugs: list[Bug], *, tolerance_lines: int = 2,
               auto_accept_enabled: bool = False) -> MatchResult:
    span = _parse_lines(flag.lines)
    if span[1] - span[0] + 1 > 200:
        return MatchResult(None, 0.0, "structural_reject", {"reason": "span_gt_200"})
    if span == (0, 0):
        return MatchResult(None, 0.0, "structural_reject", {"reason": "bad_lines"})

    candidates: list[tuple[float, Bug]] = []
    for bug in bugs:
        anchors = list(bug.line_anchors) + list(bug.aliases)
        best = 0.0
        hit = False
        for anchor in anchors:
            afile = anchor.get("file") or bug.canonical_file
            if afile != flag.file:
                continue
            a_lines = _parse_lines(str(anchor.get("lines", "")))
            if a_lines == (0, 0):
                continue
            if _overlap(span, a_lines, tolerance_lines):
                hit = True
                anchor_len = max(1, a_lines[1] - a_lines[0] + 1)
                reported_len = max(1, span[1] - span[0] + 1)
                inter = max(0, min(span[1], a_lines[1]) - max(span[0], a_lines[0]) + 1)
                best = max(best, inter / anchor_len if anchor_len else 0.0)
                _ = reported_len  # informational
        # multi-location: ≥ ceil(0.5 × related) matched
        if flag.related:
            matched_rel = sum(
                1 for r in flag.related
                if any(
                    (r.get("file") == (a.get("file") or bug.canonical_file))
                    and _overlap(_parse_lines(str(r.get("lines", ""))), _parse_lines(str(a.get("lines", ""))), tolerance_lines)
                    for a in anchors
                )
            )
            if matched_rel < math.ceil(0.5 * len(flag.related)):
                hit = False
        if hit:
            conf = min(1.0, best + (0.1 if (bug.category and flag_matches_category(flag, bug)) else 0.0))
            candidates.append((round(conf, 3), bug))

    if not candidates:
        return MatchResult(None, 0.0, "needs_review", {"reason": "NO_CANDIDATE"})

    candidates.sort(key=lambda c: (-c[0], c[1].award_unit_id))  # deterministic order
    conf, bug = candidates[0]
    outcome = "auto_accept" if (auto_accept_enabled and conf >= 0.9) else "needs_review"
    return MatchResult(
        bug.award_unit_id, conf, outcome,
        {
            "matcher_version": MATCHER_VERSION,
            "rule_set_hash": rule_set_hash(),
            "candidates": [(c, b.award_unit_id) for c, b in candidates],
            "anchor_overlap": conf,
        },
    )


def flag_matches_category(flag: Flag, bug: Bug) -> bool:
    """Category agreement raises confidence; it never decides alone (02 §9.2 #4)."""
    text = (flag.explanation or "").lower()
    return bool(bug.category and bug.category.replace("_", " ") in text)


def evaluate_submission(*, flags: list[Flag], bugs: list[Bug], auto_accept_enabled: bool = False) -> dict:
    """Full evaluation record per 11.4 data contract."""
    results = [match_flag(f, bugs, auto_accept_enabled=auto_accept_enabled) for f in flags]
    seen_units: dict[str, MatchResult] = {}
    duplicates = []
    for f, r in zip(flags, results, strict=False):
        _ = f  # flag context kept for evidence logging
        if r.award_unit_id:
            if r.award_unit_id in seen_units:
                duplicates.append(r.award_unit_id)
            else:
                seen_units[r.award_unit_id] = r
    return {
        "engine_version": MATCHER_VERSION,
        "rule_set_hash": rule_set_hash(),
        "outcome": (
            "accept_full" if results and all(r.outcome == "auto_accept" for r in results) and auto_accept_enabled
            else "needs_review"
        ),
        "matched_bug_id": (results[0].award_unit_id if results and results[0].award_unit_id else None),
        "features": {"duplicates_in_submission": duplicates},
        "confidence": max((r.confidence for r in results), default=0.0),
        "per_flag": [
            {"outcome": r.outcome, "award_unit_id": r.award_unit_id, "confidence": r.confidence}
            for r in results
        ],
    }


def points_for(unit_points: float, *, ai_share: float, ai_score: float, output_fraction: float,
               weight_multiplier: float = 1.0) -> dict[str, float]:
    """Component scoring (02 §9.4/E.4): platform computes points; model NEVER returns points."""
    base = unit_points * weight_multiplier
    ai_points = min(base * ai_share * max(0.0, min(1.0, ai_score)), base * ai_share)
    output_points = base * (1 - ai_share) * max(0.0, min(1.0, output_fraction))
    return {"ai": round(ai_points, 2), "output": round(output_points, 2)}
