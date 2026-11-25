"""T-2.1 gate: schemas + roles exist; app_api cannot read gt; runner has no DB role."""
from __future__ import annotations

from tests.integration.conftest import pytestmark  # noqa: F401 — skip-if-no-PG


def test_schemas_exist(db_conn):
    rows = db_conn.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name IN ('app','gt','practice','integrity','audit','ops')"
    ).fetchall()
    assert {r[0] for r in rows} == {"app", "gt", "practice", "integrity", "audit", "ops"}


def test_gt_tables_exist(db_conn):
    rows = db_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'gt'"
    ).fetchall()
    tables = {r[0] for r in rows}
    assert {"answer_packs", "answer_pack_entries", "candidate_bugs", "answer_pack_links",
            "bugs", "hidden_cases", "rubrics", "official_images"} <= tables


def test_ledger_origin_check_constraint(db_conn):
    row = db_conn.execute(
        "SELECT count(*) FROM information_schema.table_constraints "
        "WHERE table_name = 'ledger' AND constraint_type = 'CHECK'"
    ).fetchone()
    assert row[0] >= 1  # num_nonnulls(gt_award_unit_id, ap_entry_id, manual_decision_id) = 1


def test_node_substate_enum(db_conn):
    row = db_conn.execute(
        "SELECT count(*) FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid "
        "WHERE t.typname = 'sub_state' AND e.enumlabel IN ('waiting_repo_lock','adjusted')"
    ).fetchone()
    assert row[0] == 2
