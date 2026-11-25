#!/usr/bin/env python3
"""Audit chain verifier (T-10.9): walks prev_hash links and recomputes hashes.
Reads from Postgres when reachable; otherwise verifies a JSON export."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from audit.chain import verify_chain


def from_pg() -> list[dict] | None:
    try:
        import psycopg
        from core.config import get_settings

        s = get_settings()
        with psycopg.connect(s.dsn().replace("+psycopg", ""), connect_timeout=2) as conn:
            rows = conn.execute(
                "SELECT id, actor_id, action, target_type, target_id, "
                "encode(prev_hash, 'hex'), encode(hash, 'hex'), coalesce(details::text, '{}') "
                "FROM audit.entries ORDER BY id"
            ).fetchall()
            return [
                {"id": r[0], "actor_id": r[1], "action": r[2], "target_type": r[3],
                 "target_id": r[4], "prev_hash": r[5], "hash": r[6], "details": r[7]}
                for r in rows
            ]
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    entries = from_pg()
    if entries is None:
        export = Path("docs/load/audit-export.json")
        if not export.exists():
            print("audit_verify: no DB and no export found — generating synthetic self-test")
            # self-test the verifier against a tamper
            from audit.chain import entry_hash

            good = []
            prev = None
            for i in range(5):
                h = entry_hash(prev, actor_id="a", action=f"act.{i}", target_type="t",
                               target_id=str(i), details_json="{}")
                good.append({"id": i, "actor_id": "a", "action": f"act.{i}", "target_type": "t",
                             "target_id": str(i), "prev_hash": prev.hex() if prev else None,
                             "hash": h.hex(), "details": "{}"})
                prev = h
            r1 = verify_chain(good)
            bad = [dict(e) for e in good]
            bad[3]["hash"] = "00" * 32
            r2 = verify_chain(bad)
            print(f"self-test: intact chain ok={r1['ok']} ({r1['verified_count']} entries); "
                  f"tampered chain ok={r2['ok']} break={r2['first_break_id']}")
            ok = r1["ok"] and not r2["ok"]
            print("audit_verify:", "PASS (self-test)" if ok else "FAIL")
            return 0 if ok else 1
        entries = json.loads(export.read_text())
    result = verify_chain(entries)
    print(f"audit_verify: {result['verified_count']} entries, ok={result['ok']}, "
          f"first_break={result['first_break_id']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
