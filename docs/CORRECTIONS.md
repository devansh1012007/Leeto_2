# CORRECTIONS.md — review findings ledger

Source: "Review of 02, 07 and 08: Findings, Patches and Missing Sections".
Status values: `pending` → `applied` | `accepted_deviation` (requires sign-off) | `wont_fix` (requires sign-off + rationale).

Severity: **B** blocker, **H** high, **M** medium, **L** low.

## Cross-document conflicts (02/07/08)

| ID | Sev | Summary | Owner phase | Status | Evidence |
|----|-----|---------|-------------|--------|----------|
| R-01 | B | Participant count must be a parameter (N), never a claim; 200 is a qualification target | 0 | applied | `docs/CAPACITY.md`; header blocks of `openapi/` + README use parametric N |
| R-02 | B | Same-host runner allowed in dev/staging only; prod runner is separate VM or off | 5 | applied | `backend/packages/runner/` env guard; compose profiles |
| R-03 | B | Answer Pack tables moved to `gt` schema; `app_api` has zero grants on `gt.*` | 2 | applied | `backend/migrations/versions/0001_initial.py` (gt tables); role test |
| R-04 | H | Unplanned-bug acceptance triggers rescore job (dry-run, two approvers, announcement, reversals), never immediate scoring | 4.5 | applied | `packages/answer_authority`, rescore job |
| R-05 | H | Request pipeline replaced: lock order idempotency → stage state → clock → quota; validation before TX | 3 | applied | `packages/submissions/pipeline.py` |
| R-06 | H | One canonical error catalog; 409 for state conflicts; no 423 anywhere | 1 | applied | `openapi/errors.yaml` |
| R-07 | H | Upload validation is an async runner job; API host never unpacks | 3 | applied | `apps/api_participant/app/routers/uploads.py` |
| R-08 | H | `POST /runs` uses allow-listed `command_id` + server draft reference; no raw code blob for levels 3–4 | 1,3 | applied | `openapi/openapi.yaml` + `routers/runs.py` |
| R-09 | H | `/state` is version-keyed with ETag; no stale pointer across workers | 1,3 | applied | `routers/state.py` (`state_versions`) |
| R-10 | H | Login limits: per-identifier 5/min + 60 s delay; per-IP 120/min (venue-friendly) | 3 | applied | `packages/auth/rate.py` |
| R-11 | H | Admin auth refuses `shared_secret` when ENV ∈ {staging, prod} | 3 | applied | `apps/api_admin` boot assertion |
| R-12 | M | Topology profile table (dev/staging/prod); prod has no published host ports | 0 | applied | README + `docker-compose.yml` |
| R-13 | M | Backups must be off-host regardless of storage kind | 6 | applied | `ops/runbooks/RB-12-restore.md` |
| R-14 | M | Repo files: `Cache-Control: private, no-store` | 1,3 | applied | `routers/repo.py` |
| R-15 | M | Idempotency retention: submit/repo-lock/upload = event + 7 days | 1,2 | applied | CONTRACTS.md + prune job |
| R-16 | M | Node pointer has sub-states + `adjusted_by`/`adjusted_reason` | 2 | applied | `participant_progress` DDL |
| R-17 | M | Health/ops endpoints, CORS, cookies, CSRF, OpenAPI exposure, time-sync, graceful shutdown, migration policy, proxy trust | 1,3 | applied | `routers/ops.py`, `packages/core/middleware.py` |
| R-18 | M | Participant routes use `stage_key` slug, not ordinal | 1,3 | applied | OpenAPI paths |
| R-19 | M | Load numbers are targets with a benchmark procedure | 6 | applied | `docs/CAPACITY.md`, `tests/load/` |

## Agentic framework (07)

| ID | Sev | Summary | Owner phase | Status | Evidence |
|----|-----|---------|-------------|--------|----------|
| R-21 | L | Reword "lose track after ~40k tokens" as context-limit rationale | 0 | applied | `skills/A5-fe-participant.md` header |
| R-22 | M | A4 references `08 §2.4` for the correction protocol | 0 | applied | `skills/A4-api-admin.md` |
| R-23 | M | Force-advance first runs auto-submit for the pending level | 3,4.5 | applied | admin force-advance service |
| R-24 | M | A7 same-host rule aligned with R-02 | 5 | applied | `skills/A7-runner.md` + runner guard |
| R-25 | M | Phase 3 ships runner + AI contract stubs | 3 | applied | `runner/stub/`, `packages/ai/stub.py` |
| R-26 | M | `06 §10` launch gate + 8 escape tests defined | 6 | applied | `tests/security/runner_escape/`, launch-gate list in GATES.md |
| R-27 | L | "Never show accepted unless the server returned 2xx" wording | 4 | applied | `frontend/packages/api-client` + sync chip |
| R-28 | M | No impersonation anywhere; admin reads participant state via admin API | 4 | applied | admin preview pages; no `/view-as` route |

## Admin deep spec (08)

| ID | Sev | Summary | Owner phase | Status | Evidence |
|----|-----|---------|-------------|--------|----------|
| R-30 | M | Answer Pack requires `ground_truth` role + step-up + two approvers to activate | 4.5 | applied | answer-authority router |
| R-31 | M | Optional per-bug `weight_multiplier` (default 1) on AP entries | 2 | applied | `gt.answer_pack_entries` |
| R-32 | M | AP entry overlapping a GT anchor rejected at insert (`AP_OVERLAP_GT` constraint trigger) | 2,4.5 | applied | migration trigger |
| R-33 | M | Ledger: three origin columns + `CHECK (num_nonnulls = 1)` | 2 | applied | `app.ledger` DDL |
| R-34 | L | Bulk confirmation types the numeral ("Type 7 to confirm") | 4 | applied | admin FE `BulkActionBar` |
| R-35 | M | `/debug/state/:pid` redacts tokens; every view audited | 4 | applied | admin debug router |
| R-36 | L | `/users` scoped by `tenant_id` | 3 | applied | admin users router |

## Patch set B (02 backend spec)

| ID | Summary | Owner phase | Status |
|----|---------|-------------|--------|
| B1 | Deployment profile header (dev/staging/prod, parametric N) | 0 | applied |
| B3 | Canonical error catalog (409 not 423) | 1 | applied |
| B4 | Idempotency retention (event + 7 days for submit/lock/upload) | 1,2 | applied |
| B5 | Topology profile table | 0,6 | applied |
| B6 | Two-phase request pipeline + lock order | 3 | applied |
| B7 | Login rate-limit table (identifier + IP) | 3 | applied |
| B8 | `/state` version-keyed cache + ETag | 1,3 | applied |
| B9 | Uploads async validation; runs `command_id` allow-list | 1,3 | applied |
| B10 | Admin auth boot assertion | 3 | applied |
| B11 | Node-pointer sub-states | 2 | applied |
| B12 | Health and ops endpoints | 1,3 | applied |

## Patch set D (07 agentic framework)

| ID | Summary | Owner phase | Status |
|----|---------|-------------|--------|
| D.1 | Reworded §1.1 + Phase 3 stubs + shared DoD + human review points | 0,3 | applied |
| D.2 | A4 force-advance auto-submits first; A7 same-host rule | 3,5 | applied |
| D.3 | A8 skill finished; A9–A11 skills added | 0 | applied |

## Patch set E (08 admin deep spec)

| ID | Summary | Owner phase | Status |
|----|---------|-------------|--------|
| E.1 | AP tables in `gt`; ledger three origin columns; activation gates | 2,4.5 | applied |
| E.2 | Accepting an unplanned bug creates a draft AP entry; scoring only on activation + rescore | 4.5 | applied |
| E.3 | Mid-event correction protocol (10 steps) | 4.5 | applied |
| E.4 | No impersonation; numeral confirm; per-bug weight; tenant scope | 4 | applied |

## Decisions & deviations

| ID | Summary | Status |
|----|---------|--------|
| D-25 | N=50 default, D1 profile; 100/200 are qualification targets only | locked (default) |
| DV-02 | Same-host runner: dev/staging only; prod refuses | enforced by code |
