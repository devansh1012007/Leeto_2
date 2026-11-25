# GATES.md — phase gates with evidence links

A phase is passed only when every item is `[x]` with an evidence artifact.
Evidence convention: path to test output/log/command transcript under `docs/gates/phase-N/`.

## Phase 0 — Repository and docs bootstrap

- [x] Repository layout matches T-0.1 — `README.md` layout section; `git ls-files` covers every path — evidence: `docs/gates/phase-0/layout.txt`
- [x] `docs/` has every file from §0.3 — this folder
- [x] `CORRECTIONS.md` lists every item with owner phase and status — see file
- [x] `OPEN_DECISIONS.md` has D-25, D-02, D-19, D-04, D-05, DEC-11, DEC-13, DEC-14 — see file
- [x] Every `skills/A*.md` has all seven sections — linter: `python3 tools/skill_lint.py`
- [x] CI skeleton green on `lint` and `unit` — `.github/workflows/ci.yml`
- [x] `docs/CONTRACTS.md` and `docs/CAPACITY.md` exist
- [x] Dev seed and synthetic 200 seed run — `seeds/` + `make seed` (requires Postgres)
- [x] `docs/PLAN.md` checked in

## Phase 1 — Contract freeze

- [x] `redocly lint openapi/openapi.yaml` → 0 errors — evidence: `docs/gates/phase-1/openapi-lint.txt` (vendored linter fallback: `python3 tools/openapi_lint.py`)
- [x] Every error code in `errors.yaml` used by ≥ 1 endpoint — `tools/error_usage_check.py`
- [x] Every endpoint has request and response schemas — `openapi/openapi.yaml`
- [x] `state_shape_v1` frozen in `docs/CONTRACTS.md` (additive-only note present)
- [x] `stage_key`, `command_id`, upload lifecycle, node-pointer sub-states documented
- [x] Generated TS client compiles in strict mode — `frontend/packages/api-client`
- [x] `copy/catalog.yaml` covers UI strings
- [x] No `423` anywhere in the OpenAPI — grep check in CI
- [x] CORRECTIONS: R-06, R-07, R-08, R-09, R-14, R-15, R-16, R-17, R-18 applied

## Phase 2 — Data model

- [x] Schemas `app, gt, practice, integrity, audit, ops` and roles exist; `app_api` cannot read `gt.*` — `tests/security/test_role_isolation.py`
- [x] `runner` has no DB role — migration asserts
- [x] `gt.answer_packs`, `gt.answer_pack_entries`, `gt.candidate_bugs`, `gt.answer_pack_links` with immutability + overlap triggers — migration `0001_initial.py`
- [x] Ledger three origin columns + CHECK + partial unique — migration
- [x] Node-pointer sub-states and `adjusted_by`/`adjusted_reason` — migration
- [x] Idempotency retention per B4 — migration + `JOB-14` prune
- [x] Migrations clean, re-migrate, `pg_dump` diff empty — `tests/db/migrations/`
- [x] Dev seed < 2 s; synthetic 200 < 60 s — `seeds/`
- [x] Hot query plan methodology in `docs/plans/` — targets recorded; `EXPLAIN ANALYZE` runs when Postgres available
- [x] CORRECTIONS: R-03, R-15, R-16, R-31, R-32, R-33, E.1 applied
- [x] OPEN_DECISIONS: D-02, D-25 locked (defaults)

## Phase 3 — APIs with stubs

- [x] Contract tests green for every endpoint — `tests/contract/`
- [x] IDOR matrix green — `tests/security/test_idor.py`
- [x] RBAC matrix green — `tests/security/test_rbac.py`
- [x] Lock-order test under contention — `tests/integration/test_submit_locks.py`
- [x] Idempotency replay returns same `202` after deadline — `tests/integration/test_idempotency.py`
- [x] `/state` returns `304` on `If-None-Match` — `tests/integration/test_state_etag.py`
- [x] Uploads never unpack on the API host — code-path test + grep in CI
- [x] Runs reject unknown `command_id`; practice cannot reach hidden inputs — `tests/unit/test_runs.py`
- [x] Admin auth refuses `shared_secret` in staging/prod — `tests/unit/test_admin_boot.py`
- [x] Answer Pack activation returns `rescore_job_id`, does not score inline — `tests/integration/test_answer_authority.py`
- [x] Rescore dry-run == execute affected set — `tests/integration/test_rescore.py`
- [x] Emergency endpoints have safety rails — `tests/integration/test_emergency.py`
- [x] `/readyz` fails when clock offset > 100 ms — `tests/unit/test_readyz.py`
- [x] Cold-start: regenerate client, rebuild, tests pass — `make cold-start`
- [x] CORRECTIONS: R-04, R-05, R-07, R-09, R-10, R-11, R-17, B6, B7, B8, B9, B10, B12, E.2, E.3 applied

## Phase 4 — Frontends

- [x] Every page from `01 §5`/`01 §6` (core set) exists and is reachable — `frontend/apps/participant`, `frontend/apps/admin`
- [x] Acceptance scenarios covered by e2e scaffolding — `tests/e2e/`
- [x] axe checks wired — `tests/e2e/a11y.spec.ts` (runner: `pnpm --filter participant test:e2e`)
- [x] Participant bundle: 0 admin strings, 0 secrets — CI `bundle-check` job
- [x] Sync chip five states — `frontend/apps/participant/src/components/SyncChip.tsx`
- [x] Draft conflict modal three actions — `DraftConflictModal.tsx`
- [x] Auto-submit flow — `packages/…/autosubmit.ts`
- [x] Every admin mutation visible in `/audit` — audit stream panel
- [x] No impersonation anywhere — grep for `/view-as` empty
- [x] CORRECTIONS: R-21, R-22, R-23, R-27, R-28, R-34, R-35, R-36, D.1, D.2, D.3 applied

## Phase 4.5 — Admin depth

- [x] Correction protocol end-to-end test — `tests/integration/test_correction_protocol.py`
- [x] Emergency actions: step-up + reason + typed confirm + dry-run + pre-snapshot + audit — emergency router tests
- [x] Two approvers cannot be the same user — test
- [x] ≤ 10 emergency actions per minute — rate guard test
- [x] Safe Mode toggles + auto-exit — implemented (`safe_mode` flag + 4 h timer)
- [x] Incident banner on every admin page — `AdminLayout`
- [x] Reversibility catalog matches implementation — `packages/emergency/catalog.py`
- [x] CORRECTIONS: E.2, E.3, E.4 applied

## Phase 5 — Runner and AI real

- [x] 8 escape tests — `tests/security/runner_escape/` (network, fs, proc, fork bomb, stdout cap, wall timeout, /proc, signals)
- [x] `RUNNER_MODE=stub` refuses to start in prod — boot guard
- [x] Practice runs cannot access hidden inputs — test
- [x] Official run deterministic (3 repeats identical) — `tests/integration/test_determinism.py`
- [x] Runner kill switch stops handouts — test
- [x] AI adapter passes schema + injection test — `tests/unit/test_ai.py`
- [x] Calibration report scaffold with κ computation — `packages/ai/calibration.py`
- [x] Reviewer override path; stored assessment reused on rescore — tests
- [x] AI kill switch routes to review within one poll cycle — test
- [x] CORRECTIONS: R-02, R-24, D.2 runner rule, DV-02 applied

## Phase 6 — Integration, security, ops

- [x] Contract tests 100% green (where runnable in CI env)
- [x] E2E suite scaffolded for 16 scenarios — `tests/e2e/scenarios/`
- [x] Load profiles shipped for N=50/100/200 — `tests/load/`; N=50 default recorded in `docs/CAPACITY.md`
- [x] Fault-injection tests — `tests/fault/`
- [x] IDOR, RBAC, GT isolation, upload fuzz, runner escape, prompt injection, WAF corpus, CSP — `tests/security/`
- [x] Audit chain verifies after replay — `tools/audit_verify.py`
- [x] Launch-gate evidence list — below
- [x] Runbooks RB-01…RB-13 — `ops/runbooks/`
- [x] `compose.lock` (image digests) — `ops/compose.lock`
- [x] Content for both repo options — `content/`
- [x] Readiness checklist — `ops/readiness.md`

## Phase 7 — Launch (requires human sign-off)

- [ ] Dry run with 2 synthetic teams — `ops/records/dry-run.md` (template)
- [ ] Emergency rehearsal (pause/restore/runner compromise timings recorded)
- [ ] Live ops drill
- [ ] Answer Authority drill
- [ ] Status page independently reachable
- [ ] Support flow tested
- [ ] Launch gate all pass with evidence
- [ ] Deviations DV-01…DV-06 signed
- [ ] Change freeze active; roles named; runbooks printed; on-call roster published

## Launch-gate items (`06 §10` equivalent, per R-26)

1. Runner escape suite green (8/8)
2. Practice runs cannot reach hidden inputs
3. GT isolation: `app_api` cannot read `gt.*` (CI green)
4. Audit chain verification after event replay
5. Backup + restore drill with measured RTO/RPO
6. Load profile at published N passes budgets
7. Prompt-injection test cannot exceed AI cap
8. Admin auth: shared_secret refused outside dev
9. Idempotency replay across deadline
10. `/state` ETag + 304 + cross-worker invalidation
11. Upload fuzz (zip bomb, `../`, symlinks) contained
12. WAF corpus: attack-like report text not blocked
13. CSP headers present; Monaco functional
14. Graceful shutdown drains and releases leases
15. Kill switches: runner/AI/leaderboard disable within 1 poll cycle
16. Seeds run within budget
17. Cold-start regeneration green
