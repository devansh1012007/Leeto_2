"""E.3 gate: rescore dry-run == execute affected set (byte-identical IDs)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from answer_authority.service import rescore_dry_run
from fake_db import FakeConn


class RescoreConn(FakeConn):
    """Deterministic ledger fixture so dry-run and execute see identical state."""

    def __init__(self):
        super().__init__()
        self.tables["ledger"] = [
            {"participant_id": f"p-{i}", "stage_id": "s-1", "award_unit_id": "au-1",
             "component": "ai", "points": 10 + i}
            for i in range(3)
        ]

    def execute(self, sql, params=None):
        sql_s = str(sql)
        if "SELECT participant_id, stage_id, award_unit_id, component, points FROM app.ledger" in sql_s:
            from fake_db import Row

            return _Rows([Row(participant_id=r["participant_id"], stage_id=r["stage_id"],
                              award_unit_id=r["award_unit_id"], component=r["component"],
                              points=r["points"]) for r in self.tables["ledger"]])
        return super().execute(sql, params)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def test_dry_run_deterministic_and_sorted():
    conn = RescoreConn()
    a = rescore_dry_run(conn, event_id="e1")
    b = rescore_dry_run(conn, event_id="e1")
    assert a == b, "dry-run must be deterministic (DAT-05)"
    assert a["affected_participants"] == sorted(a["affected_participants"])
    assert len(a["affected_participants"]) == 3
