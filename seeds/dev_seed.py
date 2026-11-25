#!/usr/bin/env python3
"""Dev seed (T-0.7): 1 tenant, 1 event, 4 stages, 2 repo options, 1 challenge per option,
2 users, 1 team (both users). Must run in < 2 s.

Runs against PG_* env vars; exits 0 with a row-count report.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

TENANT = str(uuid.uuid4())
EVENT = str(uuid.uuid4())
USER_A = str(uuid.uuid4())   # lead
USER_B = str(uuid.uuid4())   # member
TEAM = str(uuid.uuid4())
STAGES = ["level_1_explain", "level_2_flags", "level_3_upload", "level_4_upload"]
OPT_A = str(uuid.uuid4())
OPT_B = str(uuid.uuid4())


async def main() -> int:
    from auth.tokens import hash_password
    from db.session import tx
    from sqlalchemy import text

    start = time.perf_counter()
    pw_hash = hash_password("dev-password-123")
    async with tx() as conn:
        conn.execute(text("INSERT INTO app.tenants (id, name) VALUES (:id, 'default_tenant')"), {"id": TENANT})
        conn.execute(
            text("INSERT INTO app.events (id, tenant_id, slug, name, tz, status) "
                 "VALUES (:id, :t, 'bug-hunt-2026', 'Bug Hunt CTF 2026', 'Asia/Kolkata', 'published')"),
            {"id": EVENT, "t": TENANT},
        )
        for i, key in enumerate(STAGES, start=1):
            conn.execute(
                text("INSERT INTO app.stages (id, tenant_id, event_id, stage_key, ordinal, name, kind, evaluator_kind, "
                     "explain_opens_at, exec_opens_at, exec_closes_at, caps, run_commands, ai_share, output_share) "
                     "VALUES (:id, :tenant, :e, :k, :i, :n, :kind, :ev, now() - interval '1 day', now() - interval '1 hour', "
                     "now() + interval '2 hours', :caps, :rc, 0.40, 0.60)"),
                {"id": str(uuid.uuid4()), "tenant": TENANT, "e": EVENT, "k": key, "i": i,
                 "n": f"Level {i}", "kind": "explain_only" if i == 1 else ("flags" if i == 2 else "upload"),
                 "ev": "match_flags" if i == 2 else ("run_tests" if i == 3 else "run_tests_and_docs"),
                 "caps": json.dumps({"max_span": 25, "max_reports_per_file": 12, "grace_s": 3}),
                 "rc": json.dumps([{"command_id": "build", "argv": ["/usr/bin/build"]},
                                   {"command_id": "test", "argv": ["/usr/bin/test"]}])},
            )
        for oid, key, title in ((OPT_A, "option_a", "Web checkout service (Python)"), (OPT_B, "option_b", "Auth service (Node)")):
            conn.execute(
                text("INSERT INTO app.repo_options (id, tenant_id, event_id, key, title) VALUES (:id, :t, :e, :k, :n)"),
                {"id": oid, "t": TENANT, "e": EVENT, "k": key, "n": title},
            )
        for opt in (OPT_A, OPT_B):
            conn.execute(
                text("INSERT INTO app.challenges (id, tenant_id, event_id, kind, lifecycle) "
                     "VALUES (:id, :t, :e, 'repo', 'published')"),
                {"id": str(uuid.uuid4()), "t": TENANT, "e": EVENT},
            )
            _ = opt
        for uid, email, role in ((USER_A, "lead@dev.local", "lead"), (USER_B, "member@dev.local", "member")):
            conn.execute(
                text("INSERT INTO app.users (id, tenant_id, email, username, password_hash, role) "
                     "VALUES (:id, :t, :e, :u, :p, 'user')"),
                {"id": uid, "t": TENANT, "e": email, "u": email.split("@")[0], "p": pw_hash},
            )
            conn.execute(
                text("INSERT INTO app.participant_progress (participant_id, tenant_id, event_id) "
                     "VALUES (:p, :t, :e)"),
                {"p": uid, "t": TENANT, "e": EVENT},
            )
        conn.execute(
            text("INSERT INTO app.teams (id, tenant_id, event_id, name) VALUES (:id, :t, :e, 'team-alpha')"),
            {"id": TEAM, "t": TENANT, "e": EVENT},
        )
        conn.execute(text("INSERT INTO app.team_members (team_id, user_id, role) VALUES (:t, :u, 'lead')"),
                     {"t": TEAM, "u": USER_A})
        conn.execute(text("INSERT INTO app.team_members (team_id, user_id, role) VALUES (:t, :u, 'member')"),
                     {"t": TEAM, "u": USER_B})
        conn.execute(text("INSERT INTO app.quota (participant_id) VALUES (:p) ON CONFLICT DO NOTHING"), {"p": USER_A})
        conn.execute(text("INSERT INTO app.quota (participant_id) VALUES (:p) ON CONFLICT DO NOTHING"), {"p": USER_B})

    elapsed = time.perf_counter() - start
    print(f"dev seed: tenant=1 event=1 stages={len(STAGES)} repo_options=2 challenges=2 users=2 teams=1 "
          f"({elapsed:.2f}s)")
    if elapsed > 2.0:
        print("FAIL: seed budget is 2 s", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
