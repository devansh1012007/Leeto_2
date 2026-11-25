# OPEN_QUESTIONS.md

Append-only. Sub-agents write ambiguities here with `BLOCKER` or `NON-BLOCKER` tags and
the documented default they proceeded with. Never silently pick.

| # | Date | Agent | Question | Tag | Default taken | Resolved |
|---|------|-------|----------|-----|---------------|----------|
| 1 | 2026-11-25 | A0 | Upstream repo `devansh1012007/Leeto_2` is private / not cloneable without credentials; repository initialized locally and prepared for push | NON-BLOCKER | Build in local git repo; push instructions in README | open |
| 2 | 2026-11-25 | A0 | Load-test qualification for N=100/200 cannot run inside the build sandbox (no live Postgres/hardware budget) | NON-BLOCKER | N=50 is the only `default` size; 100/200 remain `to_qualify` in `docs/CAPACITY.md`; scripts shipped in `tests/load/` | open |
| 3 | 2026-11-25 | A0 | Cloudflare Access is not provisionable from the build sandbox | NON-BLOCKER | `ADMIN_AUTH_MODE=shared_secret` allowed only in `ENV=dev`; boot assertion refuses it in staging/prod (B10). Access integration documented in `ops/runbooks/` | open |
