"""Unit: matcher determinism + thresholds (02 §9.2, coverage target)."""
from __future__ import annotations

import pytest
from evaluation.matcher import Bug, Flag, evaluate_submission, match_flag, points_for


def _bug(file="src/auth.py", lines="40-45", **kw):
    return Bug(award_unit_id=kw.pop("uid", "au_1"), canonical_file=file,
               line_anchors=[{"file": file, "lines": lines}], **kw)


class TestMatchFlag:
    def test_exact_hit_is_candidate(self):
        r = match_flag(Flag(file="src/auth.py", lines="42-43", explanation="null check missing"), [_bug()])
        assert r.award_unit_id == "au_1"
        assert r.outcome == "needs_review"  # auto-accept off by default

    def test_tolerance_two_lines(self):
        r = match_flag(Flag(file="src/auth.py", lines="46-48", explanation="x"), [_bug()])
        assert r.award_unit_id == "au_1"  # within ±2

    def test_out_of_range_no_candidate(self):
        r = match_flag(Flag(file="src/auth.py", lines="100-110", explanation="x"), [_bug()])
        assert r.outcome == "needs_review"
        assert r.evidence["reason"] == "NO_CANDIDATE"

    def test_wrong_file_no_candidate(self):
        r = match_flag(Flag(file="src/other.py", lines="41-42", explanation="x"), [_bug()])
        assert r.evidence["reason"] == "NO_CANDIDATE"

    def test_span_gt_200_structural_reject(self):
        r = match_flag(Flag(file="src/auth.py", lines="1-250", explanation="x"), [_bug()])
        assert r.outcome == "structural_reject"

    def test_bad_lines_structural_reject(self):
        r = match_flag(Flag(file="src/auth.py", lines="abc", explanation="x"), [_bug()])
        assert r.outcome == "structural_reject"

    def test_auto_accept_only_when_enabled_and_confident(self):
        flag = Flag(file="src/auth.py", lines="40-45", explanation="bug near auth lines")
        assert match_flag(flag, [_bug()], auto_accept_enabled=True).outcome == "auto_accept"
        assert match_flag(flag, [_bug()], auto_accept_enabled=False).outcome == "needs_review"

    def test_alias_matches(self):
        bug = _bug()
        bug.aliases = [{"file": "src/auth_v2.py", "lines": "10-12"}]
        r = match_flag(Flag(file="src/auth_v2.py", lines="11", explanation="x"), [bug])
        assert r.award_unit_id == "au_1"

    def test_deterministic_replay_identical(self):
        flag = Flag(file="src/auth.py", lines="41-44", explanation="determinism check")
        bugs = [_bug(), _bug(uid="au_2", lines="90-95")]
        a = [match_flag(flag, bugs) for _ in range(5)]
        assert all(x.outcome == a[0].outcome and x.award_unit_id == a[0].award_unit_id for x in a)

    def test_multi_location_needs_half(self):
        bug = _bug()
        flag = Flag(file="src/auth.py", lines="41-42", explanation="x",
                    related=[{"file": "src/a.py", "lines": "5-6"},
                             {"file": "src/b.py", "lines": "50-60"}])  # only 1 of 2 matches → below ceil(0.5*2)=1? 1>=1 ok
        r = match_flag(flag, [bug])
        # related matching uses bug anchors; src/a.py doesn't match any anchor → hit stays False
        assert r.award_unit_id is None


class TestScoring:
    def test_points_capped_by_ai_share(self):
        p = points_for(30.0, ai_share=0.4, ai_score=1.0, output_fraction=1.0)
        assert p["ai"] == pytest.approx(12.0)      # 30 * 0.4 * 1.0
        assert p["output"] == pytest.approx(18.0)  # 30 * 0.6 * 1.0

    def test_weight_multiplier_applies_to_base(self):
        p = points_for(30.0, ai_share=0.4, ai_score=1.0, output_fraction=0.0, weight_multiplier=2.0)
        assert p["ai"] == pytest.approx(24.0)

    def test_overflow_clamped(self):
        p = points_for(30.0, ai_share=0.4, ai_score=7.0, output_fraction=-3.0)
        assert p["ai"] == pytest.approx(12.0)
        assert p["output"] == 0.0


class TestEvaluateSubmission:
    def test_duplicate_award_units_counted_once(self):
        bugs = [_bug()]
        flags = [Flag(file="src/auth.py", lines="41-42", explanation="x"),
                 Flag(file="src/auth.py", lines="43-44", explanation="y")]
        rec = evaluate_submission(flags=flags, bugs=bugs)
        assert rec["features"]["duplicates_in_submission"] == ["au_1"]

    def test_record_carries_versions(self):
        rec = evaluate_submission(flags=[], bugs=[])
        assert rec["engine_version"] and rec["rule_set_hash"]
