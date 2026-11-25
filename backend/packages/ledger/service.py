"""Append-only ledger service (E.1/R-33/R-04). Corrections are reversal/adjustment entries;
existing rows are never mutated or deleted. Team-level dedupe per D-02 via ledger_claims.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from core.errors import ApiError
from sqlalchemy import text

Component = Literal["ai", "output", "manual"]
Origin = Literal["gt", "ap", "manual"]


@dataclass
class LedgerEntryIn:
    tenant_id: str
    event_id: str
    participant_id: str
    team_id: str | None
    stage_id: str
    award_unit_id: str
    component: Component
    points: float
    submission_id: str | None = None
    rule_version: str = "1.0.0"
    reversal_of: str | None = None
    origin: Origin = "gt"


async def append(conn, entry: LedgerEntryIn) -> str:
    """Append one entry; exactly-one-origin columns set from `origin` (R-33).

    The partial unique index (participant, stage, award_unit, component) WHERE reversal_of
    IS NULL is the real duplicate-award guard — the DB, not this code (DAT-01)."""
    origin_cols = {
        "gt": {"gt_award_unit_id": entry.award_unit_id, "ap_entry_id": None, "manual_decision_id": None},
        "ap": {"gt_award_unit_id": None, "ap_entry_id": entry.award_unit_id, "manual_decision_id": None},
        "manual": {"gt_award_unit_id": None, "ap_entry_id": None, "manual_decision_id": str(uuid.uuid4())},
    }[entry.origin]

    # team-level dedupe (D-02): first participant to earn the award claims it for the team
    if entry.team_id and not entry.reversal_of:
        claim = conn.execute(
            text("SELECT first_participant_id FROM app.ledger_claims "
                 "WHERE team_id = :t AND stage_id = :s AND award_unit_id = :a"),
            {"t": entry.team_id, "s": entry.stage_id, "a": entry.award_unit_id},
        ).first()
        if claim and str(claim[0]) != entry.participant_id:
            raise ApiError("ALREADY_SUBMITTED",
                           details={"reason": "team_dedupe", "claimed_by": str(claim[0])})

    entry_id = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO app.ledger (id, tenant_id, event_id, participant_id, team_id, stage_id, "
             "award_unit_id, component, points, submission_id, rule_version, reversal_of, "
             "gt_award_unit_id, ap_entry_id, manual_decision_id) "
             "VALUES (:id, :tenant, :event, :p, :team, :stage, :unit, :component, :points, :sub, :rv, :rev, "
             ":gtu, :ape, :md)"),
        {"id": entry_id, "tenant": entry.tenant_id, "event": entry.event_id, "p": entry.participant_id,
         "team": entry.team_id, "stage": entry.stage_id, "unit": entry.award_unit_id,
         "component": entry.component, "points": entry.points, "sub": entry.submission_id,
         "rv": entry.rule_version, "rev": entry.reversal_of, **origin_cols},
    )
    if entry.team_id and not entry.reversal_of:
        conn.execute(
            text("INSERT INTO app.ledger_claims (team_id, stage_id, award_unit_id, first_participant_id, first_ledger_id) "
                 "VALUES (:t, :s, :a, :p, :l) ON CONFLICT DO NOTHING"),
            {"t": entry.team_id, "s": entry.stage_id, "a": entry.award_unit_id,
             "p": entry.participant_id, "l": entry_id},
        )
    # bump score + leaderboard versions so /state ETag changes (R-09/B8)
    conn.execute(
        text("INSERT INTO app.state_versions (participant_id, event_id, score_version, progress_version) "
             "VALUES (:p, :e, 1, 1) ON CONFLICT (participant_id, event_id) "
             "DO UPDATE SET score_version = app.state_versions.score_version + 1"),
        {"p": entry.participant_id, "e": entry.event_id},
    )
    return entry_id


async def reverse(conn, *, entry_id: str, reason: str) -> str:
    """Reversal entry referencing the original; points negated (E.3 rescore protocol)."""
    orig = conn.execute(
        text("SELECT tenant_id, event_id, participant_id, team_id, stage_id, award_unit_id, component, points, "
             "gt_award_unit_id, ap_entry_id, manual_decision_id FROM app.ledger WHERE id = :id"),
        {"id": entry_id},
    ).first()
    if orig is None:
        raise ApiError("NOT_FOUND")
    already = conn.execute(
        text("SELECT id FROM app.ledger WHERE reversal_of = :id"), {"id": entry_id}
    ).first()
    if already:
        raise ApiError("IDEMPOTENCY_CONFLICT", details={"reason": "already_reversed"})
    new_id = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO app.ledger (id, tenant_id, event_id, participant_id, team_id, stage_id, award_unit_id, "
             "component, points, rule_version, reversal_of, gt_award_unit_id, ap_entry_id, manual_decision_id) "
             "VALUES (:id, :tenant, :event, :p, :team, :stage, :unit, :component, :points, 'rescore', :rev, "
             ":gtu, :ape, :md)"),
        {"id": new_id, "tenant": orig.tenant_id, "event": orig.event_id, "p": orig.participant_id,
         "team": orig.team_id, "stage": orig.stage_id, "unit": orig.award_unit_id,
         "component": orig.component, "points": -float(orig.points), "rev": entry_id,
         "gtu": orig.gt_award_unit_id, "ape": orig.ap_entry_id, "md": orig.manual_decision_id},
    )
    conn.execute(
        text("INSERT INTO audit.entries (event_id, actor_id, actor_role, action, target_type, target_id, details) "
             "VALUES (:e, NULL, 'system', 'ledger.reverse', 'ledger_entry', :id, :d)"),
        {"e": orig.event_id, "id": entry_id, "d": f'{{"reason":"{reason}"}}'},
    )
    return new_id
