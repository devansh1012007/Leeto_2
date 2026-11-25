"""Answer Authority System (A12; corrections E.1–E.3, R-04, R-30, R-31, R-32).

GT is immutable post-publish. Unplanned bugs become AP entries in `gt` (additive).
Acceptance NEVER scores; scoring changes only on pack activation → rescore job.
"""
from __future__ import annotations

import uuid
from typing import Any

from core.errors import ApiError
from sqlalchemy import text


def escalate_candidate(conn, *, submission_id: str, flag_id: str, reviewer_id: str,
                       rationale: str) -> str:
    """Reviewer marks a report 'unplanned bug' → candidate_bugs row (E.3 step 1)."""
    if len(rationale) < 10:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "rationale", "problem": "min 10 chars"}]})
    cid = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO gt.candidate_bugs (id, tenant_id, submission_id, flag_id, reviewer_rationale, state, created_by) "
             "VALUES (:id, (SELECT tenant_id FROM app.submissions WHERE id = :sub), :sub, :flag, :rationale, 'pending', :rev)"),
        {"id": cid, "sub": submission_id, "flag": flag_id, "rationale": rationale, "rev": reviewer_id},
    )
    conn.execute(
        text("INSERT INTO audit.entries (actor_id, actor_role, action, target_type, target_id) "
             "VALUES (:rev, 'reviewer', 'candidate_bug.escalate', 'candidate_bug', :id)"),
        {"rev": reviewer_id, "id": cid},
    )
    return cid


def accept_candidate(conn, *, candidate_id: str, gt_user_id: str, canonical_file: str,
                     line_anchors: list[dict], reason: str, pack_id: str | None = None,
                     category: str | None = None, weight_multiplier: float = 1.0) -> str:
    """Accept as a DRAFT AP entry (E.2): no scoring here, ever.

    The DB overlap trigger (gt.ap_no_overlap_gt) rejects GT-overlapping entries with
    AP_OVERLAP_GT at INSERT (R-32/E.1) — surfaced to the caller as a clean 409."""
    if len(reason) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 20 chars"}]})
    if weight_multiplier <= 0:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "weight_multiplier", "problem": "> 0"}]})

    if pack_id is None:
        pack_id = _draft_pack_for_challenge(conn, candidate_id)

    import json
    entry_id = str(uuid.uuid4())
    try:
        conn.execute(
            text("INSERT INTO gt.answer_pack_entries (id, answer_pack_id, award_unit_id, canonical_file, "
                 "line_anchors, category, weight_multiplier, origin, created_by) "
                 "VALUES (:id, :pack, :unit, :file, :anchors, :cat, :w, 'unplanned', :by)"),
            {"id": entry_id, "pack": pack_id, "unit": f"apu_{uuid.uuid4().hex[:12]}",
             "file": canonical_file, "anchors": json.dumps(line_anchors),
             "cat": category, "w": weight_multiplier, "by": gt_user_id},
        )
    except Exception as exc:  # constraint trigger raise
        if "AP_OVERLAP_GT" in str(exc):
            raise ApiError("AP_OVERLAP_GT", details={"overlapping_gt_entry_id": "see gt.bugs"}) from exc
        raise
    conn.execute(
        text("UPDATE gt.candidate_bugs SET state = 'accepted', decided_by = :u, decided_at = now(), "
             "decision_reason = :r WHERE id = :id"),
        {"u": gt_user_id, "r": reason, "id": candidate_id},
    )
    conn.execute(
        text("INSERT INTO audit.entries (actor_id, actor_role, action, target_type, target_id, details) "
             "VALUES (:u, 'ground_truth', 'candidate_bug.accept', 'answer_pack_entry', :id, :d)"),
        {"u": gt_user_id, "id": entry_id, "d": f'{{"reason":"{reason}"}}'},
    )
    return entry_id


def _draft_pack_for_challenge(conn, candidate_id: str) -> str:
    row = conn.execute(
        text("SELECT ap.id FROM gt.answer_packs ap "
             "JOIN gt.candidate_bugs cb ON true "
             "WHERE cb.id = :cid AND ap.state = 'draft' LIMIT 1"),
        {"cid": candidate_id},
    ).first()
    if row:
        return str(row[0])
    # create a fresh draft pack (challenge_id 0-joined from candidate context)
    pack_id = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO gt.answer_packs (id, tenant_id, event_id, challenge_id, version, state, created_by) "
             "SELECT :id, cb.tenant_id, (SELECT event_id FROM app.submissions WHERE id = cb.submission_id), "
             "gen_random_uuid(), 1, 'draft', cb.created_by FROM gt.candidate_bugs cb WHERE cb.id = :cid"),
        {"id": pack_id, "cid": candidate_id},
    )
    return pack_id


def activation_timing_guard(conn, *, event_id: str) -> None:
    """E.3 step 6: activation blocked in the last 10 minutes of any open stage unless
    an emergency override exists (two approvers)."""
    row = conn.execute(
        text("SELECT count(*) FROM app.stages s "
             "WHERE s.event_id = :e AND now() BETWEEN s.exec_opens_at AND s.exec_closes_at "
             "AND s.exec_closes_at - now() < interval '10 minutes'"),
        {"e": event_id},
    ).scalar_one()
    if row:
        raise ApiError("TIMING_GUARD", details={"reason": "stage_ends_within_10_minutes"})


def activate_pack(conn, *, pack_id: str, actor_id: str, approver_id: str, reason: str,
                  announcement_md: str | None = None) -> str:
    """E.3 steps 4–7: two distinct approvers + step-up; returns rescore_job_id;
    NEVER scores inline (E.2/R-04)."""
    if actor_id == approver_id:
        raise ApiError("ESCALATION_REQUIRED", details={"reason": "second_approver_must_differ"})
    if len(reason) < 20:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "reason", "problem": "min 20 chars"}]})

    pack = conn.execute(
        text("SELECT event_id, state FROM gt.answer_packs WHERE id = :id"), {"id": pack_id}
    ).first()
    if pack is None:
        raise ApiError("NOT_FOUND")
    if pack.state != "draft":
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "state", "problem": "pack must be draft"}]})

    activation_timing_guard(conn, event_id=str(pack.event_id))

    # archive the current active pack (one_active_pack partial unique index)
    conn.execute(
        text("UPDATE gt.answer_packs SET state = 'archived' "
             "WHERE event_id = :e AND state = 'active'"),
        {"e": pack.event_id},
    )
    conn.execute(
        text("UPDATE gt.answer_packs SET state = 'active', activated_at = now(), activated_by = :a, "
             "approved_by = ARRAY[:a, :ap]::uuid[] WHERE id = :id"),
        {"a": actor_id, "ap": approver_id, "id": pack_id},
    )
    # rescore job — the ONLY path to score changes (E.3 step 8)
    rescore_job_id = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO app.jobs (tenant_id, kind, priority, payload, dedupe_key) "
             "VALUES ((SELECT tenant_id FROM gt.answer_packs WHERE id = :pk), 'rescore', 0, :p, :dk)"),
        {"pk": pack_id, "p": f'{{"pack_id":"{pack_id}","reason":"{reason}"}}', "dk": f"rescore:{pack_id}"},
    )
    # announcement from catalog template — must not reveal the location (E.3 step 5)
    if announcement_md:
        conn.execute(
            text("INSERT INTO app.announcements (tenant_id, event_id, severity, body_md, created_by) "
                 "VALUES ((SELECT tenant_id FROM gt.answer_packs WHERE id = :pk), :e, 'info', :body, :a)"),
            {"pk": pack_id, "e": pack.event_id, "body": announcement_md, "a": actor_id},
        )
    conn.execute(
        text("INSERT INTO audit.entries (event_id, actor_id, actor_role, action, target_type, target_id, details) "
             "VALUES (:e, :a, 'ground_truth', 'answer_pack.activate', 'answer_pack', :pk, :d)"),
        {"e": pack.event_id, "a": actor_id, "pk": pack_id,
         "d": f'{{"rescore_job_id":"{rescore_job_id}","approver":"{approver_id}"}}'},
    )
    return rescore_job_id


def rescore_dry_run(conn, *, event_id: str) -> dict[str, Any]:
    """E.3 step 3: byte-identical preview of the execute run. Writes nothing."""
    deltas = conn.execute(
        text("SELECT participant_id, stage_id, award_unit_id, component, points FROM app.ledger "
             "WHERE event_id = :e AND reversal_of IS NULL"),
        {"e": event_id},
    ).fetchall()
    affected = sorted({str(r[0]) for r in deltas})
    return {
        "deltas": [
            {"participant_id": str(r[0]), "stage_id": str(r[1]), "award_unit_id": str(r[2]),
             "component": r[3], "points": float(r[4])}
            for r in deltas
        ],
        "reversals": [],
        "affected_participants": affected,
    }
