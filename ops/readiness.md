# Readiness checklist (A-33) — publication blocked while required items are unchecked

| # | Item | Owner | Evidence | State |
|---|------|-------|----------|-------|
| 1 | Every S1 blind-spot mitigation implemented + verified | A0 | docs/GATES.md launch-gate list | pending |
| 2 | Load test at N=50 passes §1.4 budgets | A9 | docs/CAPACITY.md | pending (scripts shipped) |
| 3 | Full dry-run with real users | A0 | ops/records/dry-run.md | pending |
| 4 | Game-day failure injections | A13 | ops/records/game-day.md | pending |
| 5 | Backup restore drill with measured RTO/RPO | A11 | ops/records/restore-drills.md | pending |
| 6 | Penetration test findings closed | A10 | docs/security/ | pending |
| 7 | Two independent reviewers certified every challenge | A12 | ops/records/challenge-review.md | pending |
| 8 | Answer-key isolation verified (app_api cannot read gt) | A10 | tests/security/test_role_isolation.py | automated |
| 9 | Rules/privacy/consent published + flows tested | A11 | content/ | pending |
| 10 | Runbooks printed; incident roles assigned | A11 | ops/runbooks/ | done (rehearsal pending) |
| 11 | Venue network tested from seats; second uplink verified | A11 | ops/records/venue.md | pending |
| 12 | Runner isolation: escape tests contained | A7 | tests/security/runner_escape/ | automated (8/8) |
| 13 | Practice runs cannot reach hidden inputs | A7 | tests/unit/test_runs.py | automated |
| 14 | AI: injection ≤ cap; stored reuse; privacy notice names provider | A8 | tests/unit/test_ai.py | automated |
| 15 | Runner + AI kill switches rehearsed; DEC-11..14 locked | A13 | docs/OPEN_DECISIONS.md | locked (defaults) |
