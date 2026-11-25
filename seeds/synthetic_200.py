#!/usr/bin/env python3
"""Synthetic 200 seed (T-0.7/T-2.9): 1 tenant, 1 event, 4 stages, 2 challenges,
200 users, 40 teams, participant_progress at random nodes. Budget: < 60 s.

Also loads the ~50-flag anonymized fixture for matcher tests (T-2.9).
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
import time
import uuid

random.seed(200)
NODES = ["LANDING", "L1_EXPLAIN", "L1_EXEC", "L1_SUBMITTED", "L2_EXPLAIN", "L2_EXEC",
         "L2_SUBMITTED", "L3_EXPLAIN", "L3_EXEC", "L3_SUBMITTED", "L4_EXPLAIN", "L4_EXEC",
         "L4_SUBMITTED", "DONE"]
N_USERS = 200
N_TEAMS = 40


async def main() -> int:
    from auth.tokens import hash_password
    from db.session import tx
    from sqlalchemy import text

    start = time.perf_counter()
    tenant = str(uuid.uuid4())
    event = str(uuid.uuid4())
    pw = hash_password("synthetic-pass-123")
    async with tx() as conn:
        conn.execute(text("INSERT INTO app.tenants (id, name) VALUES (:id, 'synthetic')"), {"id": tenant})
        conn.execute(
            text("INSERT INTO app.events (id, tenant_id, slug, name, status) VALUES (:id, :t, 'synthetic-200', 'Synthetic 200', 'live')"),
            {"id": event, "t": tenant},
        )
        for i in range(1, 5):
            conn.execute(
                text("INSERT INTO app.stages (id, tenant_id, event_id, stage_key, ordinal, name, kind, evaluator_kind) "
                     "VALUES (:id, :t, :e, :k, :i, :n, :kind, 'match_flags')"),
                {"id": str(uuid.uuid4()), "t": tenant, "e": event,
                 "k": f"level_{i}_{'explain' if i == 1 else 'flags'}", "i": i, "n": f"L{i}",
                 "kind": "explain_only" if i == 1 else "flags"},
            )
        for c in range(2):
            conn.execute(
                text("INSERT INTO app.challenges (id, tenant_id, event_id, kind, lifecycle) "
                     "VALUES (:id, :t, :e, 'repo', 'published')"),
                {"id": str(uuid.uuid4()), "t": tenant, "e": event},
            )
        # users + teams in bulk for speed
        users = [(str(uuid.uuid4()), f"user{i:03d}@synthetic.local", f"user{i:03d}") for i in range(N_USERS)]
        teams = [(str(uuid.uuid4()), f"team-{i:02d}") for i in range(N_TEAMS)]
        conn.execute(
            text("INSERT INTO app.users (id, tenant_id, email, username, password_hash, role) "
                 "VALUES (:id, :t, :e, :u, :p, 'user')"),
            [{"id": u, "t": tenant, "e": e, "u": n, "p": pw} for u, e, n in users],
        )
        conn.execute(
            text("INSERT INTO app.teams (id, tenant_id, event_id, name) VALUES (:id, :t, :e, :n)"),
            [{"id": t, "t": tenant, "e": event, "n": n} for t, n in teams],
        )
        # 5 members per team, first is lead
        member_rows = []
        for ti, (tid, _) in enumerate(teams):
            for j in range(5):
                uid = users[ti * 5 + j][0]
                member_rows.append({"t": tid, "u": uid, "r": "lead" if j == 0 else "member"})
        conn.execute(
            text("INSERT INTO app.team_members (team_id, user_id, role) VALUES (:t, :u, :r)"),
            member_rows,
        )
        conn.execute(
            text("INSERT INTO app.participant_progress (participant_id, tenant_id, event_id, node, sub_state, version) "
                 "VALUES (:p, :t, :e, :n, 'active', 1)"),
            [{"p": u, "t": tenant, "e": event, "n": random.choice(NODES)} for u, _, _ in users],
        )
        conn.execute(
            text("INSERT INTO app.quota (participant_id) VALUES (:p) ON CONFLICT DO NOTHING"),
            [{"p": u} for u, _, _ in users],
        )
        # ~50 realistic anonymized flags for matcher tests (T-2.9)
        flag_rows = []
        sid = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO app.submissions (id, tenant_id, participant_id, stage_id, kind, status, receipt_code) "
                 "VALUES (:id, :t, :p, (SELECT id FROM app.stages WHERE event_id = :e AND ordinal = 2), "
                 "'flags', 'received', :rc)"),
            {"id": sid, "t": tenant, "p": users[0][0], "e": event, "rc": "FIXT-0001"},
        )
        for i in range(50):
            flag_rows.append({
                "id": str(uuid.uuid4()), "t": tenant, "s": sid, "o": i,
                "loc": json.dumps([{"file": f"src/mod{i % 7}.py", "lines": f"{10 + i % 30}-{12 + i % 30}"}]),
                "exp": f"anonymized explanation {i}",
            })
        conn.execute(
            text("INSERT INTO app.flags (id, tenant_id, submission_id, ordinal, locations, explanation) "
                 "VALUES (:id, :t, :s, :o, :loc, :exp)"),
            flag_rows,
        )

    elapsed = time.perf_counter() - start
    print(f"synthetic seed: users={N_USERS} teams={N_TEAMS} flags=50 ({elapsed:.2f}s)")
    if elapsed > 60:
        print("FAIL: seed budget is 60 s", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
