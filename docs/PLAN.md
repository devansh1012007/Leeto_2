# `docs/PLAN.md` — Master Execution Plan

> **Audience:** coding agents (orchestrator A0 and sub-agents A1–A13).
> **What to do with this file:** save it at `docs/PLAN.md` in the repo root. It is the top-level execution plan. Every sub-agent reads it before starting, plus the files under `docs/` (§0.3) and its own `skills/Axx.md`.
> **Authority:** if this plan contradicts `02`, `07`, `08`, or the review findings, **the review findings win** (they are the corrections). If it contradicts the architecture or `03-specification`, **the architecture wins** until an ADR changes it.
> **Ambiguity rule:** if a sub-agent finds an ambiguity not resolved here, it writes it in `docs/OPEN_QUESTIONS.md`, tags it `BLOCKER` or `NON-BLOCKER`, and proceeds with the documented default. Never silently pick.

---

## §0 — How this plan is used

### §0.1 Six conventions

1. **Phases are strictly sequential at the gate.** A0 may run sub-agents inside a phase in parallel. A phase gate is not passed until every item on the gate list is checked with an evidence artifact linked in `docs/GATES.md`.
2. **Every agent produces file artifacts, not chat.** A handoff is a file path plus a link to the acceptance evidence. A0 does not accept "done" without both.
3. **Every change to a frozen contract wakes the consumers.** `openapi/openapi.yaml`, `openapi/errors.yaml`, `copy/catalog.yaml`, `docs/CONTRACTS.md`, `03_Database_Spec.md`, and `docs/CORRECTIONS.md` are watched. A0 re-runs the affected gates.
4. **Corrections from the review (R-01…R-36, D-25, B1…B12, §13, D.1–D.3, E.1–E.4) are non-negotiable.** They are listed in `docs/CORRECTIONS.md` with a status table; the phase ledger in §12 tracks them.
5. **The participant count is a parameter (`N`)**, not a claim. Default to `N=50`. `N=100` and `N=200` are **qualification targets**; they are only promoted to the published cap after the load profile in `04 §8` passes at that size. No document, comment, log, or marketing copy may state a size that has not passed.
6. **When in doubt, fail closed.** If a request path cannot determine authorization, return `403`/`404`, never `200`. If a background job cannot confirm completion, leave it `leased`, never `done`.

### §0.2 Definition of Done — one file, one source

`docs/DEFINITION_OF_DONE.md` is created in Phase 0 and referenced by every phase gate. It contains:

- **Per-agent DoD template:** build green, tests green, no warnings, no TODOs in new code, no secrets, no `print`, error paths covered, accessibility checked (frontend), role test passed (backend).
- **Per-phase DoD:** every task card in the phase is `pass`; every correction tagged to that phase is `applied`; every gate item has evidence.
- **Global DoD for the product:** all 16 acceptance scenarios from `01 §7`, all launch-gate items from `06 §10`, all correction items from `docs/CORRECTIONS.md` `applied`, all supported-N declarations backed by load test evidence.

### §0.3 The docs folder every agent reads

A0 creates these before any code is written. They are the shared memory across phases.

```
docs/
  PLAN.md                  this file
  DEFINITION_OF_DONE.md    per-agent and per-phase DoD
  CORRECTIONS.md           R-01…R-36, D-25, B1…B12, D.1–D.3, E.1–E.4 with status
  OPEN_DECISIONS.md        D-02, D-25, and every decision not yet locked
  OPEN_QUESTIONS.md        questions raised by sub-agents (append-only)
  CONTRACTS.md             frozen contracts: /state shape, error catalog, upload protocol, run command_id, stage_key, node-pointer sub-states
  GATES.md                 phase gates with evidence links
  HANDOFF.md               handoff template (below)
  CAPACITY.md              the parametric N and the load-test procedure
  INCIDENT_PLAYBOOK.md     (Phase 6 onward) how to run the launch rehearsal
  RUNBOOK_INDEX.md         (Phase 6) links to ops/runbooks/*
```

### §0.4 Handoff template (`docs/HANDOFF.md`)

Every handoff artifact from every agent includes:

```
# Handoff: <agent> -> <next-agent> (phase P)

## Outputs
- <path 1>  (<one line what it is>)
- <path 2>  ...

## Acceptance evidence
- <test run URL or log path>
- <screenshot or rendered artifact if frontend>
- <openapi lint output if contract>

## Corrections applied
- R-xx: <how it was applied, file/line>
- ...

## Assumptions
- <thing the next agent must know that is not obvious from the spec>

## Questions
- <open question, if any, with default taken>
```

---

## §1 — Decisions to lock before Phase 0

These are cross-phase blockers. Each is a **human decision**; A0 will not accept a phase gate until each is written in `docs/OPEN_DECISIONS.md` with a signed answer.

| ID | Question | Default if unanswered | Impact |
|----|----------|-----------------------|--------|
| **D-25** | Target participant count `N` and hosting profile | `N=50`, single VM + separate runner VM (D1) | `00` AS-01, load budget, compute budget |
| **D-02** | Team-level vs participant-level award dedupe | Team-level dedupe (per `07` review R-04 recommendation) | Ledger schema, matcher, review UI |
| **D-19** | Single active session per participant? | Yes, with supersession | Auth, session table, `/state` |
| **D-04/D-05** | Level 3/4 scoring model | Level 3 hidden tests + Level 4 test-catch credit + AI on docs (per `02` §9.3 proposal) | Evaluator, rubric, ledger components |
| **DEC-11** | AI `ai_share` per stage | `0.4` for stages with `ai_share>0` | Scoring, calibration |
| **DEC-13** | AI provider | `local` (Ollama-compatible) for D0/D1; `remote` requires privacy notice | `packages/ai`, privacy notice, egress |
| **DEC-14** | Runner hosting | Separate VM in prod; same-host container **only** dev/staging with no real data | Topology, runner skill |
| **R-02 / D.2** | Same-host runner allowed? | **No** in prod. Off if separate VM unavailable | Scoring fallback mode |

A0 will block Phase 5 on `DEC-13` and `DEC-14` if unresolved.

---

## §2 — Phase 0: Repository and docs bootstrap

**Goal:** every subsequent phase has a place to work, every sub-agent has a place to read from, every gate has a place to write evidence.

**Agents involved:** A0 (owns). All other agents read-only during Phase 0.

### §2.1 Task cards

**T-0.1 — Repository layout** (A0)
Create the monorepo per `01 §1.2` with these corrections applied:
- `backend/apps/{api_participant,api_admin,worker_general,worker_evaluator,scheduler,runner_gateway,runner}/`
- `backend/packages/{core,db,auth,events,teams,progress,drafts,submissions,evaluation,runs,ledger,leaderboard,review,integrity,audit,storage,ai,runner,answer_authority,emergency}/`
- `frontend/apps/{participant,admin}/`
- `frontend/packages/{api-client,ui,workspace,clock,storage,validation,copy,config}/`
- `runner/` (image + protocol client only; no DB)
- `openapi/`, `schemas/`, `copy/`, `docs/`, `skills/`, `ops/runbooks/`, `content/`, `tests/`
- CI at `.github/workflows/` (or equivalent) with the checks listed in §2.2.

Acceptance: `git ls-files` shows every path; `README.md` documents the layout; a stub build for each app compiles.

**T-0.2 — Docs folder** (A0)
Create every file listed in §0.3. Each file has at least its heading, purpose, and owner. `CORRECTIONS.md` is populated **now** with the full correction list (§12 of this plan, copied verbatim) with status `pending` for every item. This is the ledger A0 checks at every gate.

Acceptance: every doc exists; `CORRECTIONS.md` lists every R-xx, B-xx, E-xx, D-xx item with an owner phase; `OPEN_DECISIONS.md` lists every D-xx.

**T-0.3 — Skills folder** (A0 + each agent)
Create `skills/A0.md` through `skills/A13.md`. A0, A1–A11 skills are copied from `07 §1.5.1–1.5.11` with **corrections D.1–D.3 applied**; A12 (Answer Authority) and A13 (Emergency) skills are from `08 §7` and the review. Every skill has: Role, Inputs, Outputs, Hard rules, Playbooks, Success criteria, Handoffs.

Acceptance: every skill exists; a linter checks that every skill has all seven sections; every skill's inputs reference only files that exist in `docs/` or the repo.

**T-0.4 — CI skeleton** (A0)
CI jobs:
- `lint` (ruff, mypy, tsc, eslint, prettier)
- `unit` (pytest, vitest)
- `integration` (Postgres testcontainers)
- `contract` (schemathesis stub against empty API — will fail until Phase 3)
- `boundaries` (`pytest -m boundaries` — will fail until Phase 3)
- `openapi-lint` (redocly)
- `bundle-check` (participant build has no admin strings/secrets)
- `role-isolation` (CI test that `app_api` cannot read `gt`)
- `security-headers` (curl test on a fixture)
- `cold-start` (delete generated client, regenerate, build) — runs from Phase 3 on
- `load-smoke` (100 req/s for 10 s against a stub) — runs from Phase 6 on

Acceptance: CI runs green on the skeleton; every job that will gate a phase has at least an `echo` that runs.

**T-0.5 — `docs/CONTRACTS.md` skeleton** (A0)
Freeze the contract index. List every endpoint group, who produces it (`A3`/`A4`), who consumes it (`A5`/`A6`/`A9`), and its lock status. Add the `state_shape` entry with `version: 1` and status `pending_phase_1`.

Acceptance: all consumers named; `state_shape` marked `pending_phase_1`; every endpoint group in `02 §6` has an entry.

**T-0.6 — `docs/CAPACITY.md`** (A0)
Freeze the parametric definition: `N ∈ {50, 100, 200}`, the process for qualifying each size, the load script locations (`tests/load/*`), and the rule that no doc/comment/log states a number that has not passed.

Acceptance: file exists; `N=50` is the only size marked `default`; every other size has a `to_qualify` line with a target date placeholder.

**T-0.7 — Dev seeds** (A2 early)
`seeds/dev_seed.py` inserts: 1 tenant, 1 event, 4 stages, 2 repo options, 1 challenge per option, 2 users, 1 team (both users). Must run in < 2 s.

`seeds/synthetic_200.py` inserts: 1 tenant, 1 event, 4 stages, 2 challenges, 200 users, 40 teams, participant_progress at random nodes.

Acceptance: dev seed runs; synthetic seed runs in < 60 s; CI has a job that runs both and asserts row counts.

### §2.2 Phase 0 gate — `docs/GATES.md` entries

- [ ] Repository layout matches §2.1 T-0.1
- [ ] `docs/` folder has every file from §0.3
- [ ] `CORRECTIONS.md` has every item with owner phase and status `pending`
- [ ] `OPEN_DECISIONS.md` has D-25, D-02, D-19, D-04, D-05, DEC-11, DEC-13, DEC-14
- [ ] Every `skills/A*.md` has all seven sections
- [ ] CI skeleton green on `lint` and `unit`
- [ ] `docs/CONTRACTS.md` and `docs/CAPACITY.md` exist
- [ ] Dev seed and synthetic 200 seed run in CI
- [ ] `docs/PLAN.md` (this file) is checked in

---

## §3 — Phase 1: Contract freeze

**Goal:** every consumer (A3, A4, A5, A6, A7, A8) works against one frozen contract. No frontend or backend code is written until the contract passes lint and the generated client builds.

**Agents involved:** A1 (owns). A0 reviews.

### §3.1 Task cards — A1

**T-1.1 — `openapi/openapi.yaml`** (all endpoints)
Cover every endpoint in `02 §6.1–§6.20`, plus:
- **`GET /state`** with the version-keyed response shape per **R-09/B8**: request accepts `If-None-Match`; response carries `ETag` that is the hash of the version tuple; the body is identical for the same tuple; `server_time` is the only field that changes per call and is added **outside** the ETag'd body.
- **`GET /state` shape** documented in `docs/CONTRACTS.md` as `state_shape_v1`, with the frozen field list. Any change requires a version bump and A0 wakes A5, A6, A9.
- **`POST /uploads`** returns `{upload_id, status:"stored"}` (no unpack, no parse) per **R-07/B9**. `POST /uploads/{id}/validate` returns `202 {job_id}`.
- **`GET /uploads/{id}`** returns `{status: stored|validating|ok|failed, problems[]}`.
- **`POST /runs`** takes `{stage_key, command_id, workspace: {draft_version} | {delta}, stdin?}` per **R-08/B9**; no code blob, no argv.
- **Stage identity**: all participant routes use `stage_key` (stable slug), not `n` per **R-18**. Add `ordinal` as an informational integer only.
- **Answer Authority** endpoints per **E.1–E.3** (under `/admin/...`).
- **Emergency** endpoints per `08 Part 4` (under `/admin/.../emergency/*` and `/admin/incidents/*`).
- **Health and ops** endpoints per **R-17/B12**: `/healthz`, `/readyz`, `/metrics` with exposure rules.
- **Admin preview** endpoints per **E.4** (no impersonation): `/admin/participants/{pid}/state`, `/admin/preview/effect`, `/admin/preview/rescore`.

**T-1.2 — `openapi/errors.yaml`** (canonical catalog)
Use the **B3** catalog verbatim. Rules:
- State conflicts are `409`, not `423`. `423 Locked` is not used.
- Every endpoint lists every error it can return.
- The catalog includes `details.waiting_on[]` for `GATE_BLOCKED`; `details.repo_choice` for `REPO_ALREADY_LOCKED`; `details.conflict` for `DRAFT_VERSION_CONFLICT`.
- `AUTH_SESSION_SUPERSEDED` (D-19) is present with a `details` field carrying the device hint if permitted.
- Every error code in `errors.yaml` is referenced by at least one endpoint; no orphan code.

**T-1.3 — `copy/catalog.yaml`**
Every user-visible string in `01 §5`, `07 §5`, and `08 Part 4` gets a key. Placeholder pool keys `placeholder.flag.N`. Warning keys `warn.deadline.5m` etc. Error display keys `error.<code>` for every error in `errors.yaml`. Admin preview strings have a separate prefix `admin.preview.*` so A5 renders participant-side strings from the same catalog.

**T-1.4 — `schemas/*.json`**
JSON schemas for `/state`, `/progress`, `/drafts`, `/stages/*/submit` (discriminated by `kind`), `/uploads` (discriminated by `status`), `/runs`, answer packs, emergency actions. Each schema has `$id`, `required`, `additionalProperties: false`, and an example.

**T-1.5 — `docs/CONTRACTS.md` finalized**
- `state_shape_v1` frozen (field list, types, nullable, meaning).
- `stage_key` pattern: `^[a-z0-9_]{3,32}$`, uniqueness per event.
- `command_id` allow-list pattern: `^[a-z][a-z0-9_]{2,32}$`; the stage config declares which are allowed.
- Upload lifecycle: `stored → validating → ok | failed`.
- Node pointer sub-states per **B11**.

**T-1.6 — Generated TS client builds**
`pnpm --filter api-client build` succeeds against the frozen OpenAPI. The client is committed so A5 and A6 can start before CI has a live server.

### §3.2 A1 hard rules

- No endpoint returns an unlisted error code.
- No request or response field lacks `description`, `example`, and constraints.
- Every response that includes time includes `server_time` in `meta`.
- Every mutation with an `Idempotency-Key` declares its replay semantics in the OpenAPI `description`.
- `POST /stages/{key}/submit` is a discriminated union: `kind: flags | upload`; both branches fully typed.
- The generated client compiles with `tsc --noEmit` in strict mode.

### §3.3 Phase 1 gate

- [ ] `redocly lint openapi/openapi.yaml` → 0 errors, 0 warnings
- [ ] Every error code in `errors.yaml` is used by ≥ 1 endpoint
- [ ] Every endpoint has request and response schemas
- [ ] `state_shape_v1` frozen in `docs/CONTRACTS.md` with an explicit "additive-only" note
- [ ] `stage_key`, `command_id`, upload lifecycle, node-pointer sub-states documented
- [ ] Generated TS client compiles in strict mode
- [ ] `copy/catalog.yaml` covers every UI string named in `01 §5`, `07 §5`, `08 Part 4`
- [ ] No `423` anywhere in the OpenAPI
- [ ] **CORRECTIONS.md:** R-06, R-07, R-08, R-09, R-14, R-15, R-16, R-17, R-18 marked `applied`

---

## §4 — Phase 2: Data model

**Goal:** every invariant from `03 §5` enforced in the database; roles and grants as specified with the corrections; seeds run; hot queries meet targets.

**Agents involved:** A2 (owns). A9 runs the role test.

### §4.1 Task cards — A2

**T-2.1 — Schemas and roles**
- Schemas: `app`, `gt`, `practice`, `integrity`, `audit`, `ops`.
- Roles: `db_owner`, `app_api`, `admin_api`, `worker`, `evaluator`, `scheduler`, `runner_gw`, `auditor`, `gt_reader`.
- **R-03/E.1 applied:** Answer Pack tables live in `gt`, not `app`. `app_api` has **zero** grants on `gt.*` (asserted by CI).
- `runner` role does not exist in the DB at all (the runner has no DB access).

**T-2.2 — Answer Pack tables in `gt`** (per **E.1**)
- `gt.answer_packs` with `one_active_pack` unique index
- `gt.answer_pack_entries` with `award_unit_id UNIQUE` and `weight_multiplier NUMERIC DEFAULT 1` (per **R-31/E.4**)
- `gt.candidate_bugs`
- `gt.answer_pack_links`
- Trigger: `answer_pack_entries` rows of `active`/`archived` packs are immutable
- Trigger: AP entry that overlaps a GT bug anchor (same file, overlapping range) is rejected at `INSERT` with `AP_OVERLAP_GT` — enforced by a constraint trigger per **R-32/E.1**

**T-2.3 — Ledger with three origin columns** (per **R-33/E.1**)
`app.ledger` adds `gt_award_unit_id uuid NULL`, `ap_entry_id uuid NULL`, `manual_decision_id uuid NULL`, with `CHECK (num_nonnulls(gt_award_unit_id, ap_entry_id, manual_decision_id) = 1)`. Partial unique index for effective non-reversal entries on `(participant_id, stage_id, award_unit_id, component)`. Immutable via `REVOKE UPDATE, DELETE` for all app roles.

**T-2.4 — Node pointer sub-states** (per **B11**)
`app.participant_progress`:
- `node` enum (base)
- `sub_state` enum: `waiting_repo_lock`, `ready`, `active`, `submitting`, `evaluating`, `evaluated`, `adjusted`
- `adjusted_by`, `adjusted_reason`, `version`, `updated_at`
- Trigger: forward-only moves on `(stage, node)`; sub_state transitions checked in code, not in a DB trigger, because sub-state is display-level.

**T-2.5 — Idempotency retention** (per **B4**)
Add `route` column, then **partial unique** on `(participant_id, route, key)` where `route ∈ {submit, repo_lock, upload, run, force_action}`. Retention: event duration + 7 days. Other routes 24 h. Prune job (`JOB-14`) reads `expires_at`.

**T-2.6 — Rate-limit and quota tables** per `03 §3.1.5`; **no in-process-only rate limits** for correctness-critical paths (submit, login, runs). In-process limits may exist as fast-path guards.

**T-2.7 — Admin and incident tables** per `08 §5.1`:
- `app.errors`, `app.admin_presence`, `app.content_revisions`, `app.cache_epoch` (from `07 §3.9`)
- `app.incidents`, `app.incidents_timeline`, `app.emergency_actions`, `app.ledger_snapshots`, `app.participant_freeze`, `app.team_quarantine`, `app.admin_impersonation` (kept for audit even though impersonation is disabled — it records attempts)
- `gt.answer_packs`, `gt.answer_pack_entries`, `gt.candidate_bugs`, `gt.answer_pack_links`
- `app.ai_assessments`, `app.ai_eval_sets`, `app.ai_overrides`

**T-2.8 — Migrations**
Alembic, expand/contract only. Every migration has a paired test in `tests/db/migrations/`. Migrations run in CI from clean, then re-run, then `pg_dump` diff must be empty.

**T-2.9 — Seeds**
- Dev seed: 2 users, 1 team, 1 event, 1 challenge per repo option, 4 stages.
- Synthetic 200: 200 users, 40 teams, 4 stages, 2 challenges, random progress.
- Anonymized fixture of ~50 realistic flags for matcher tests.

**T-2.10 — Hot query plans** (per `03 §9`)
Every query in `03 §9` has a file in `docs/plans/` with `EXPLAIN ANALYZE` output on the synthetic 200 dataset. Target times per `03 §9`. Missing or exceeding target → red gate.

### §4.2 Phase 2 gate

- [ ] All schemas and roles exist; `app_api` cannot read `gt.*` (CI test green)
- [ ] `runner` has no DB access (asserted: no role, no grants)
- [ ] `gt.answer_packs`, `gt.answer_pack_entries`, `gt.candidate_bugs`, `gt.answer_pack_links` exist with immutability + overlap triggers
- [ ] Ledger three origin columns + CHECK + partial unique exist
- [ ] Node-pointer sub-states and `adjusted_by`/`adjusted_reason` exist
- [ ] Idempotency retention per B4
- [ ] Migrations clean, re-migrate, `pg_dump` diff empty
- [ ] Dev seed < 2 s; synthetic 200 < 60 s
- [ ] Every hot query plan file exists and meets target
- [ ] **CORRECTIONS.md:** R-03, R-15, R-16, R-31, R-32, R-33, E.1 marked `applied`
- [ ] **OPEN_DECISIONS:** D-02, D-25 marked `locked` (or `BLOCKED` with a plan)

---

## §5 — Phase 3: APIs with stubs for runner and AI

**Goal:** A3 (participant API) and A4 (admin API) are implemented against the Phase 1 contract. A7 and A8 provide **contract-adherent stubs** so A3 can integrate run and AI endpoints before the real runner and AI are ready.

**Agents involved:** A3, A4, A7 (stub), A8 (stub). A9 runs contract + boundary checks.

### §5.1 Task cards — A7 stub first (so A3 can code against it)

**T-3.0 — Runner stub** (A7)
- Implements `POST /runner/claim`, `POST /runner/jobs/{id}/heartbeat`, `POST /runner/jobs/{id}/result` (per `02 §10.2`).
- Behaves like a runner that accepts a job, sleeps for a deterministic delay, and returns a **canned** result set indexed by `job_id` hash.
- No execution. No sandbox. No shell.
- Rejects jobs whose `image_digest` is not in a fixture list.
- Stub is served on the runner's private port; gateway points at it via `RUNNER_STUB=1`.
- Stub is guarded: `ENV=prod` refuses to start in stub mode.

**T-3.0b — AI stub** (A8)
- Implements `AiAssessor.assess(request) -> result` per `02 §9.4` and `08 Part 3` output schema.
- Returns deterministic criteria_met from a canned fixture keyed by `input_hash`.
- Refuses to return anything with `points` in the output (schema forbids it).
- Stub is `AI_KIND=stub` and refuses in prod.

**Acceptance for T-3.0, T-3.0b:** contract test hits the stub through the gateway; A3's run and AI paths are testable end-to-end.

### §5.2 Task cards — A3 (participant API)

**T-3.1 — Request pipeline** per **B6**
Two phases. **Lock order:** `idempotency → stage state → team/participant progress → quota`. Read-only requests skip the transaction entirely (short statement timeout). Every mutation test asserts lock order does not invert under contention.

**T-3.2 — Auth and sessions** per `02 §6.1` + **B7** + **R-10**
- Per-identifier limit 5/min sliding + 60 s delay after 5 failures in 10 min (no hard lockout).
- Per-IP limit 120/min (venue-friendly).
- Argon2id semaphore = vCPU count.
- `/auth/refresh` rotation with Web Locks-compatible `pg_advisory_lock` per session.
- D-19 supersession returns `AUTH_SESSION_SUPERSEDED` (B3) with no user enumeration.

**T-3.3 — `/state`** per **B8** + `state_shape_v1`
- Reads a `state_versions` record.
- In-process cache keyed by version tuple.
- `ETag` = hash of tuple; `If-None-Match` → `304`.
- `server_time` is always fresh.
- Cache invalidation across workers is via the version tuple, not a broadcast. A worker with a stale key can never serve a stale pointer.
- The payload matches `state_shape_v1` **exactly**; any extra field fails CI.

**T-3.4 — Submit transaction** per **B6** + `02 §9.5`
- All steps in §5 of B6 in a single transaction.
- `clock_timestamp()` read once **after** locking stage state.
- Writes `submission`, `flags` (if kind=flags), `submission_artifact` (if kind=upload), `evaluation_event`, `job:evaluate`, `outbox`, `audit_chain` — all in one TX.
- `202` includes `receipt_id`, `accepted_at`, `server_time`.
- Replay of same idempotency key returns original `202` **even after the deadline** (B4).
- Submit with `kind=upload` requires `upload.status=ok` or `validation=deferred` if runner unavailable (`UPSTREAM_UNAVAILABLE` with a documented grace).

**T-3.5 — Uploads** per **B9**
- `POST /uploads`: stream to disk, magic check, sha256, store, `status:"stored"`.
- `POST /uploads/{id}/validate`: enqueue `upload_validate` job; `202 {job_id}`.
- `GET /uploads/{id}`: `status ∈ {stored, validating, ok, failed}`.
- No unpacking on the API host; the job runs on the runner.

**T-3.6 — Runs** per **B9**
- `POST /runs` with `{stage_key, command_id, workspace}`. `command_id` must be in the stage's allow-list.
- Per-participant concurrency 1; runs/min from config.
- Global admission queue with max depth; over limit → `RUN_RATE_LIMITED` with `details.estimated_wait`.
- Never accepts raw code for levels 3–4; only `draft_version` reference or a delta ≤ 256 KB.
- Practice mode uses a separate `command_id` namespace; hidden inputs never reach it (`06 §5` invariant).

**T-3.7 — Drafts** per `02 §6.8`
- `PUT /drafts/{stage_key}` with `If-Match`. `409 DRAFT_VERSION_CONFLICT` on stale.
- Merge on the server is 3-way; conflicts go back to the client with the two versions.
- Size cap 512 KB; over → `413 DRAFT_TOO_LARGE`.

**T-3.8 — Repo** per `02 §6.5`
- `GET /repo/files/{path}` `Cache-Control: private, no-store` (per **R-14**).
- Watermark applied on the fly; line numbers preserved.
- `GET /repo/search` rate-limited 20/min; `403` if the runner is off is **not** correct — search is server-side and does not need the runner.

**T-3.9 — Gate** per `02 §6.7`
- Reads `app.gate_hint` (2 s stale max). Entry request re-checks against live state, not the hint. `GATE_BLOCKED` returns `details.waiting_on[]` names.

**T-3.10 — Admin preview and read-only participant view** per **E.4** (A3 side)
- `GET /admin/participants/{pid}/state` returns the participant's state to the admin API only (token scope check). Tokens, cookies, outbox contents are redacted.

**T-3.11 — Health and ops** per **R-17/B12**
- `/healthz`, `/readyz`, `/metrics` on the internal network only.
- `/readyz` fails if DB unreachable, schema < head, clock offset > 100 ms, disk > threshold.

**T-3.12 — Platform hygiene** per `02 §13`
- CORS allow-list, cookies (`__Secure-` prefix; `Path=/v1/auth`), CSRF `Origin` + custom header, HSTS, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: private, no-store`.
- Interactive OpenAPI docs disabled in staging/prod.
- Proxy-header trust: `CF-Connecting-IP` only from the Tunnel network; else peer address.
- Graceful shutdown: stop accepting, drain 30 s, release leases.
- Migrations not auto-run on boot; app refuses if schema older than required.

**T-3.13 — Rate limits** per `02 §11`
Every limit is a DB row for the correctness-critical ones (submit, login, runs). In-process buckets are fast-path only. Every 429 returns `Retry-After`.

### §5.3 Task cards — A4 (admin API)

**T-4.1 — Admin auth** per **B10**
- `ADMIN_AUTH_MODE ∈ {access, shared_secret}`.
- **Refuses to start** if `ENV ∈ {staging, prod}` and mode is `shared_secret`.
- Access assertion validated (audience, issuer, expiry, signature via cached JWKS).
- App MFA required regardless.
- Step-up token valid 5 min; admin mutation endpoints require it when configured.

**T-4.2 — Admin endpoints** from `02 §6.13–§6.20`
Every mutation: permission check + reason (where listed) + audit + `Idempotency-Key` for retryable ones. No exceptions.

**T-4.3 — Answer Authority endpoints** per **E.1–E.3**
- `POST /admin/challenges/{id}/answer-packs` (from GT)
- `POST /admin/answer-packs/{id}/activate` (requires `ground_truth` + step-up + two approvers) — **does not score immediately**; returns `{rescore_job_id}`.
- `POST /admin/answer-packs/{id}/entries` (origin `unplanned`)
- `POST /admin/answer-packs/{id}/entries/{eid}/link` (creates ledger entry with `ap_entry_id`)
- `GET /admin/challenges/{id}/candidate-bugs`
- `POST /admin/candidate-bugs/{id}/accept` — creates a **draft** AP entry (per **E.2**, no scoring yet)
- `POST /admin/candidate-bugs/{id}/reject {reason}`

**T-4.4 — Rescore job** per **E.3**
- `POST /admin/events/{id}/rescore/dry-run` → `{deltas, reversals, affected_participants}`; byte-identical to execute's affected set.
- `POST /admin/events/{id}/rescore/execute` → step-up + two approvers + reason + typed `RESCORE`.
- Every ledger change is a reversal or adjustment; **no deletes**.
- On AP activation, the rescore runs automatically with the protocol from E.3; every step is a `correction_id` linked in audit.

**T-4.5 — Emergency endpoints** per `08 Part 4` + the safety rails in `08 §4.12`
- Every emergency endpoint is under `/admin/.../emergency/*` or `/admin/incidents/*`.
- Requires step-up (fresh < 5 min).
- Destructive actions require two approvers (a different `organizer` user).
- Reason string ≥ 20 chars.
- Typed confirmation (numeral per **R-34**).
- `dry_run` available where side effects exist; `pre_action_snapshot` written before score changes.
- Participant copy comes from the catalog, not free text.
- 60 s auto-revert where the action is reversible.
- No more than 10 emergency actions per minute per event.

**T-4.6 — Incidents** per `08 §4.8`
`POST /admin/incidents`, `/update`, `/resolve`, `/assign`, `/step`. `IncidentBanner` reads from the same endpoint.

**T-4.7 — Admin live console aggregate**
`GET /admin/events/{id}/live` returns the shape required by `07 §3.1` (counters per stage, queue age, error rate, runner health, AI health). This endpoint reads aggregates, not per-participant rows.

**T-4.8 — Effect preview**
`POST /admin/preview/effect {action, payload}` returns `{participant_copy[], scope, duration, undo, render_hint}`. A6 renders with participant components.

### §5.4 Phase 3 gate

- [ ] Contract tests green for every endpoint in `openapi/openapi.yaml`
- [ ] IDOR matrix green across participants and teams (A10 runs it)
- [ ] RBAC matrix green (`06 §2`)
- [ ] **Lock order** test green under contention (B6)
- [ ] Idempotency replay returns same `202` after deadline (B4)
- [ ] `/state` returns `304` on `If-None-Match`; version tuple invalidation works across 2 workers (B8)
- [ ] Uploads never unpack on the API host (grep the code path + integration test)
- [ ] Runs reject unknown `command_id`; practice cannot reach hidden inputs
- [ ] Admin auth refuses `shared_secret` in `ENV ∈ {staging, prod}` (B10)
- [ ] Answer Pack activation returns `rescore_job_id`, does **not** score inline (E.2)
- [ ] Rescore dry-run == execute affected set (byte-identical IDs)
- [ ] Emergency endpoints have all safety rails (step-up, two approvers, reason, typed confirm, dry-run, snapshot, participant copy from catalog) — tested per endpoint
- [ ] `/readyz` fails when clock offset > 100 ms
- [ ] Cold-start test: delete generated TS client, regenerate, build, all contract tests still pass
- [ ] **CORRECTIONS.md:** R-04, R-05, R-07, R-09, R-10, R-11, R-17, B6, B7, B8, B9, B10, B12, E.2, E.3 marked `applied`

---

## §6 — Phase 4: Frontends

**Goal:** A5 (participant FE) and A6 (admin FE) implemented against the frozen Phase 1 client. Both apps share `packages/ui` and the copy catalog.

**Agents involved:** A5, A6 (parallel). A9 runs e2e.

### §6.1 Task cards — A5 (participant FE)

**T-5.1 — Boot sequence** per `07 §5.2`
Every step has an error path. `/config.json` failure falls back to build defaults with one log line. Clock failure shows a non-blocking warning. Client-too-old blocks the workspace but not informational pages.

**T-5.2 — Route guards** per `07 §5.3`
Guard routes, never decides allow. `/stages/{key}/gate` decides on entry.

**T-5.3 — Every page from `01 §5` P-01…P-24** with the state machines from `07 §5.4`. Pages without a state machine in `07` (P-01, P-02, P-04, P-06, P-17, P-18, P-21, P-22) get a state machine per the DoD: loading, empty, error, offline, ready.

**T-5.4 — Sync chip** per `02 §2.6` + `07 §5.4.4`
States: `Saved locally`, `Saved to server`, `Offline: changes kept on this device`, `Submit queued, not accepted yet`, `Submission accepted`. A queued submit is **never** displayed as accepted.

**T-5.5 — Draft conflict modal** per `07 §5.4.5`
Default action `Keep mine` per `07` (log the choice), with an extra confirm when `Keep mine` is chosen. Focus trap. No `Esc`-to-nothing.

**T-5.6 — Auto-submit flow** per `07 §5.4.4`
Warnings at 5/3/1 min. At 0: modal, flush via `sendBeacon`, poll `/state` at 1 s until pointer advances. After 60 s: message with `request_id` and safe-close message.

**T-5.7 — Reduced-motion** per `07 §7.6`
Every animation gated. Reduced-motion mode also gates the focus-return animation (per `07 Part 8 §8.4` point 1). The a11y test suite runs in both modes.

**T-5.8 — Offline banner** per `07 §5.4.9`
Debounced 3 s. Outbox flush on online. Chip becomes `Saved to server` when confirmed.

**T-5.9 — Cross-tab** per `07 §5.4.10`
`BroadcastChannel` events. Web Locks for refresh. Second tab read-only in editing.

**T-5.10 — Keyboard contract** per `07 §5.6`
Full list implemented; `?`, `r`, `l` suppressed when focus is in an editable element.

**T-5.11 — Bundle discipline**
Participant build contains **zero** admin strings, zero `gt` content, zero secrets. CI grep runs as a gate. `01 §1.3` budgets enforced by Vite plugin + CI check.

**T-5.12 — Accessibility**
`axe-core` on every page in light and dark. 0 criticals. Keyboard-only run of every page. Screen-reader pass on: sign-in, consent, dashboard, workspace header, progress bar (both states), flag form, all modals, receipt. Focus return on reduced-motion (the `07` Part 8 §8.4 gap).

**T-5.13 — Admin preview rendering**
A5 exports `packages/ui` components that A6 uses for `EffectPreview`. The component API is documented in `packages/ui/README.md` with a stable `preview` prop.

### §6.2 Task cards — A6 (admin FE)

**T-6.1 — Admin shell** per `08 §1.2`
Top bar, left nav, page header, global status strip. `CommandPalette` (C-80) with `⌘K`.

**T-6.2 — Every page from `01 §6` A-01…A-35** plus `08 §1.1.1–§1.1.8` (including `Emergency`, `Answer Authority`, `Incident`, `Preview`, `Debug`).

**T-6.3 — `EffectPreview` (C-81) everywhere**
Rendered from `POST /admin/preview/effect`. Uses the participant components from `packages/ui`.

**T-6.4 — `ApprovalFlow` (C-82)**
Two-approver UI. Second approver must be a **different** user; UI blocks picking self. Approver sees the diff and the announcement draft.

**T-6.5 — `EmergencyPanel` (C-83) + `BulkActionBar` (C-91)**
Every emergency action goes through the five-layer safety rail. Bulk confirmation is "Type 7 to confirm" (numeral per **R-34**).

**T-6.6 — Answer Authority console (C-97)** per `08 §2.3.4` with **E.1–E.3** corrections:
- Pack list; activation button goes through approval flow; activation returns a `rescore_job_id` and shows a progress panel.
- Link report creates a ledger entry; display shows the `ap_entry_id` and reason.
- Compare with GT shows non-overlapping entries; overlapping entries are blocked at creation with a clear error.

**T-6.7 — AI pipeline viewer (C-98)** per `08 Part 3`
Stage-by-stage timeline. Reviewer can click a stage to see prompt and output. Override panel writes `app.ai_overrides` per criterion.

**T-6.8 — No impersonation** per **R-28/E.4**
Admin reads participant state via `GET /admin/participants/{pid}/state` and renders in admin components. The participant SPA never runs in the admin origin. `Debug /state` redacts tokens.

**T-6.9 — Audit visibility**
Every mutation shows up in `/audit` within 2 s. Every admin page shows last-refresh time and manual refresh.

**T-6.10 — Incident banner (C-94)** on every admin page while an incident is active.

**T-6.11 — Live console (C-94, C-95, C-93)** per `07 §3` and `08 §1.2`:
2 s ticker, degraded state, stale badge > 10 s, error stream, kill switch tiles, log stream with `request_id` copy.

**T-6.12 — Accessibility (admin, best-effort AA)**
Keyboard pass on every admin page; screen reader pass on the emergency room and the review workbench.

**T-6.13 — Preview pages** per `08 §1.1.8`
`/preview/participant/:pid`, `/preview/as-if/:scenario`, `/debug/state/:pid`. All audited. `/debug/state` shows redacted payload only.

### §6.3 Phase 4 gate

- [ ] Every page from `01 §5` and `01 §6` (plus `08 §1.1` additions) exists and is reachable
- [ ] 16 acceptance scenarios from `01 §7` pass in Playwright against the real stack
- [ ] `axe-core` 0 criticals on every participant page (light + dark) and every admin page
- [ ] Keyboard-only run of every page passes
- [ ] Focus return works under reduced-motion
- [ ] Participant bundle: 0 admin strings, 0 secrets, size within budget
- [ ] Sync chip has all five states and reflects server truth
- [ ] Draft conflict modal has three actions and no data loss path
- [ ] Auto-submit flow tested with network drop and browser closed
- [ ] Every admin mutation visible in `/audit` within 2 s
- [ ] `EffectPreview` renders correctly for every admin action that has participant effect
- [ ] No impersonation anywhere (grep for `/view-as` in admin FE is empty)
- [ ] **CORRECTIONS.md:** R-21, R-22, R-23, R-27, R-28, R-34, R-35, R-36, D.1, D.2, D.3 marked `applied`

---

## §7 — Phase 4.5: Admin depth (A12, A13)

**Goal:** the two new agents from `08` (Answer Authority + Emergency) deliver their specialized console and rehearse the protocols.

**Agents involved:** A12, A13. A4 and A6 integrate the new endpoints and pages.

### §7.1 Task cards — A12 (Answer Authority)

**T-7.1 — Full AAS** per `08 §2`
- Console per `08 §2.3.4` with corrections.
- Candidate bug queue per `08 §2.2.3` + **E.2**.
- Correction protocol per **E.3**: escalate → evaluate → dry run → approve → announce → timing guard → activate → rescore → publish → audit.

**T-7.2 — AP-↔-GT overlap** per **R-32/E.1**
Constraint trigger blocks overlaps at insert. UI shows a clear error and links to the overlapping GT entry (with `ground_truth` permission check).

**T-7.3 — Announcement in correction protocol**
Announcement must not reveal the new bug's location. Copy catalog has a fixed template `correction.unplanned.accepted` with only the count of additional issues.

**T-7.4 — End-to-end test** of the correction protocol with a fixture bug reported by a participant:
1. Reviewer escalates
2. GT drafts AP entry
3. Dry run shows the new score for reporter + N other participants
4. Two approvers activate
5. Rescore runs
6. Ledger has reversal (if any) + new entries with `ap_entry_id`
7. Audit chain verifies
8. Leaderboard version bumps

### §7.2 Task cards — A13 (Emergency)

**T-7.5 — Emergency room** per `08 §4`
Every power, every safety rail.

**T-7.6 — Safe Mode** per `08 §4.10`
Master switch. Non-essential endpoints 503. `/state` lite. Workspace read-only. Auto-exit after 4 h with alert.

**T-7.7 — Incident management** per `08 §4.8`
Declare, update, resolve, assign, step. `IncidentBanner` renders on every admin page.

**T-7.8 — PIR** per `08 §4.11`
Auto-drafted at resolve; reviewable; exportable.

**T-7.9 — Reversibility catalog** per `08 §4.9`
Every action declares undo window, reversal method, participant notification. UI surfaces all three before confirmation.

**T-7.10 — Emergency rehearsal** (this is a Phase 7 item too, but A13 builds the tool now)
Three scenarios reproducible with fixtures: pause, restore, runner compromise.

### §7.3 Phase 4.5 gate

- [ ] Correction protocol end-to-end test green (T-7.4)
- [ ] Every emergency action: step-up + reason + typed confirm + dry-run where applicable + pre-snapshot + audit
- [ ] Two approvers cannot be the same user (test)
- [ ] No more than 10 emergency actions per minute (test)
- [ ] Safe Mode toggles correctly and auto-exits
- [ ] Incident banner visible on every admin page while active
- [ ] PIR generates from a fixture incident
- [ ] Reversibility catalog matches the implementation for every action
- [ ] **CORRECTIONS.md:** E.2, E.3, E.4 marked `applied`; D-25 dependency verified (N in capacity doc is consistent)

---

## §8 — Phase 5: Runner and AI real

**Goal:** replace stubs with the real implementations. This is the only phase where the runner is allowed to execute code, and the only phase where the AI provider is called.

**Agents involved:** A7, A8. A9 runs integration and load.

### §8.1 Task cards — A7 (runner real)

**T-8.1 — Topology** per **R-02/D.2** + `02 §10.1`
- Gateway on the main VM; runner on its **own VM** with no internet route.
- Runner **pulls**: opens connections to the gateway; no inbound ports.
- Mutual TLS **or** signed per-runner token (choose one; document in `06 §5`).
- `RUNNER_MODE ∈ {off, stub, real}`. In `prod`, `stub` is refused. In `dev`/`staging` with no real data, `real` on the same host is allowed with a warning banner.

**T-8.2 — Protocol** per `02 §10.2`
`POST /runner/claim`, heartbeat, result. The runner never receives storage credentials. Files are short-lived signed URLs from the gateway. Hidden inputs on tmpfs during official runs, scrubbed after.

**T-8.3 — Sandbox** per `02 §10.3`
- Namespaces: user, mount, pid, net.
- cgroup v2: cpu.max, memory.max, pids.max, io limits.
- seccomp default-deny + allow-list.
- Read-only base snapshot; tmpfs workspace.
- Wall timeout kill on process tree.
- Output capped; truncation marker set.
- Scrub `tmpfs` between runs (per **GAP-03**).

**T-8.4 — Escape tests** (the 8 from `06 §5`)
1. `curl https://…` fails (no egress)
2. `ping 8.8.8.8` fails
3. `cat /etc/passwd` fails
4. Fork bomb is contained
5. 1 GB stdout is truncated, host unaffected
6. Infinite loop killed at wall timeout
7. `/proc` read fails
8. Signal outside namespace fails

All 8 must pass in CI. Failure blocks release.

**T-8.5 — Admission control** per `02 §10.5`
Global queue cap; official jobs > practice; round-robin per team; one concurrent per participant. Kill switch stops handouts.

**T-8.6 — Runner stub removal**
A7 removes the stub and confirms A3's run endpoints now use the real protocol. Any drift in the protocol between Phase 3 and Phase 5 is a `BLOCKER` bug, not a "next sprint" item.

### §8.2 Task cards — A8 (AI real)

**T-8.7 — Provider adapter** per `02 §9.4` + `08 Part 3`
- `assess(request) -> result` interface.
- Local provider (Ollama-compatible) is default. Remote provider requires `AI_KIND=remote` and a `privacy_notice_version` bump.
- Timeout 30 s, 2 retries, concurrency 4, spend budget with hard stop, kill switch.
- Never returns points. Only criteria_met + reasoning_chain + evidence + confidence + safety_flags.

**T-8.8 — Reasoning chain** per `08 Part 3`
8 reasoning steps (restate, locate, evidence, root cause test, criterion loop, contradictions, alternates, judgement). Chain length capped. Persisted as `reasoning_chain_md`.

**T-8.9 — Evidence extraction** per `08 §3.7`
Every `met=true` requires ≥ 1 report quote and ≥ 1 code quote. Quotes validated as verbatim substrings; failures downgrade the criterion to `unclear`.

**T-8.10 — Confidence scoring** per `08 §3.9`
Model confidence + heuristic confidence. Combined < 0.55 → review. Contradiction + alternate + low model confidence → review.

**T-8.11 — Output validation** per `08 §3.10`
Schema + quote verbatim + rubric ID allow-list. Retry once, then `NEEDS_REVIEW` with raw output stored.

**T-8.12 — Calibration gate** per `08 §3.12` + review **R-11?** (calibration is per `08`; the review accepted it)
- Golden set per award unit.
- Precision ≥ 0.9, recall ≥ 0.85 per criterion, κ ≥ 0.6.
- Run before freeze. Non-passing criterion → reduce `ai_share` for the stage, or rewrite the rubric.
- Report attached to the freeze.

**T-8.13 — Injection test** per `06 §5` + `08 Part 3`
Prompt-injection test set cannot produce points above the cap. Malformed output routes to review. The model never receives the full GT.

**T-8.14 — Store and reuse** per `08 §3.11`
Stored per `(submission_id, award_unit_id, prompt_hash, rubric_hash, model_version)`. Rescore **never** re-calls the model. Reviewer override replaces the criterion's credit; the assessment stays.

**T-8.15 — AI kill switch** routes new assessments to review within one poll cycle.

### §8.3 Phase 5 gate

- [ ] 8 escape tests pass; runner on separate VM in `prod` (verified by deployment check)
- [ ] `RUNNER_MODE=stub` refuses to start in `prod`
- [ ] Practice runs cannot access hidden inputs (test)
- [ ] Official run is deterministic (3 repeats identical)
- [ ] Runner kill switch stops handouts within 1 s
- [ ] AI provider adapter passes schema and injection test
- [ ] Calibration report: κ ≥ 0.6 per criterion for every stage with `ai_share>0`
- [ ] Reviewer override path tested; stored assessment reused on rescore
- [ ] AI kill switch routes to review within 1 poll cycle
- [ ] **CORRECTIONS.md:** R-02, R-24, D.2 runner rule, DV-02 marked `applied` (or `accepted_deviation` with sign-off)

---

## §9 — Phase 6: Integration, security, ops

**Goal:** everything works together at `N`, at scale, under fault; the security posture is proven; ops is ready.

**Agents involved:** A9, A10, A11.

### §9.1 Task cards — A9 (integration)

**T-9.1 — Contract tests** generated from OpenAPI. Every endpoint, every error code. `schemathesis` fuzz green.

**T-9.2 — E2E suite** (Playwright, real stack):
- Full four-level journey with 2 users in one team
- Refresh and Dashboard round-trips
- Offline during submit
- Auto-submit at deadline
- Unauthorized URL access

**T-9.3 — Load profiles** per `04 §8` for `N=50`, `N=100`, `N=200`:
- Login burst
- T0 content burst
- Steady-state polling
- Submission peak
- Leaderboard refresh
- Run burst
- Run abuse
- AI scoring burst
- Soak (30 min)
- DB failure + recovery
- Restore drill (runs with A11)

**T-9.4 — Fault injection** per `02 §12`:
- Kill API after commit before response
- Kill a worker mid-lease
- Restart Postgres under load

**T-9.5 — Cold-start test** (already gating Phase 3; run again here with everything integrated).

**T-9.6 — Record the qualified `N`** in `docs/CAPACITY.md`. Publish only the largest passing size. Update `00 AS-01`, `01 §1.3`, `04 §8` to match.

### §9.2 Task cards — A10 (security)

**T-10.1 — IDOR matrix** across every `/v1` route.
**T-10.2 — RBAC matrix** per `06 §2`.
**T-10.3 — GT isolation** with the real role.
**T-10.4 — Upload fuzz** (`../`, symlinks, zip bomb, 4 GB expansion) on the runner.
**T-10.5 — Runner escape suite** (already gating Phase 5).
**T-10.6 — Prompt-injection test set** (already gating Phase 5).
**T-10.7 — WAF corpus test** — SQL/XSS/shell text in reports not blocked.
**T-10.8 — CSP test** — Monaco works; inline scripts blocked.
**T-10.9 — Audit chain verification** after a full event replay.
**T-10.10 — Launch gate evidence** per `06 §10`, one artifact per item.

### §9.3 Task cards — A11 (ops + content)

**T-11.1 — Runbooks RB-01 … RB-13** per `05 §8`. Each: trigger, owner, steps, verification, rollback. Offline-printable.

**T-11.2 — Content** for `(stage, repo option)` — explanations, guides, rules, event details. Both repo options equal depth.

**T-11.3 — `compose.lock`** — image digests pinned. CI compares on every deploy.

**T-11.4 — Backup and restore drill** — measured RTO and RPO. Recorded in `ops/records/`.

**T-11.5 — Readiness checklist** (A-33) — items with owner, evidence link, state.

**T-11.6 — Status page** — off-host, reachable independently.

### §9.4 Phase 6 gate

- [ ] Contract tests 100% green
- [ ] E2E 16 scenarios green in Chrome, Edge, Firefox
- [ ] Load profile passes at `N`; `N` recorded in `docs/CAPACITY.md`
- [ ] Fault injection: no false 200s; recovery within targets
- [ ] Cold-start green
- [ ] IDOR, RBAC, GT isolation, upload fuzz, runner escape, prompt injection, WAF, CSP all green
- [ ] Audit chain verifies after full event replay
- [ ] Every launch-gate item in `06 §10` has an evidence artifact
- [ ] Every runbook rehearsed; dates in `ops/records/`
- [ ] Restore drill recorded with measured RTO and RPO
- [ ] `compose.lock` pinned; digests match deployment
- [ ] Content frozen for both repo options
- [ ] Readiness checklist signed
- [ ] **CORRECTIONS.md:** all items marked `applied` or `accepted_deviation` with sign-off

---

## §10 — Phase 7: Rehearsal and launch

**Goal:** the actual dry run. Two synthetic teams complete all four levels. Every emergency scenario rehearsed. Final launch gate.

**Agents involved:** A0 (runs), A9, A10, A11, A12, A13. Human sign-off required.

### §10.1 Task cards

**T-12.1 — Full dry run with 2 teams** (all 4 levels, submit, receipt, results).

**T-12.2 — Emergency rehearsal** with the incident commander role:
- RB-02 pause/resume: measure time-to-effect for all participants
- RB-12 restore: measure RTO/RPO against the drill target
- RB-10 runner compromise: measure time from kill switch to rebuilt runner

**T-12.3 — Live ops console drill**: the operator role walks through live monitoring, drill-down, force-action with preview, and answers "what is happening right now?" from the console without opening logs.

**T-12.4 — Answer Authority drill**: an unplanned bug escalates and activates end-to-end with the two-approver flow, scoring the reporter correctly, with audit chain verify after.

**T-12.5 — Status page drill**: verify the off-host status page is reachable independently of the main host.

**T-12.6 — Support flow**: synthetic participant submits a support ticket; support resolves it; the `request_id` trace is complete.

**T-12.7 — Launch gate** — every item in `06 §10` and every item in `docs/DEFINITION_OF_DONE.md` `Global DoD` is `pass` with evidence.

**T-12.8 — Named D0 deviations** signed:
- DV-01 (admin Access bypass) — **only** if `ENV=staging` with no real data; `prod` refuses (B10)
- DV-02 (same-host runner) — **not allowed in prod**; documented in dev/staging
- DV-03 (single host durability) — accepted with restore drill evidence
- DV-04 (local object storage) — only if MinIO not available; encrypted backups
- DV-05 (local AI) — default; remote requires privacy notice update
- DV-06 (polling only) — accepted

### §10.2 Phase 7 gate — Launch

- [ ] Dry run complete
- [ ] Emergency rehearsal: time-to-effect measured for 3 scenarios
- [ ] Live ops drill: operator answers "what is happening?" from the console
- [ ] AAS drill: unplanned bug end-to-end with audit verify
- [ ] Status page reachable independently
- [ ] Support flow tested
- [ ] Launch gate all pass with evidence
- [ ] Every deviation signed
- [ ] Change freeze active
- [ ] Roles named on A-33
- [ ] Runbooks printed offline
- [ ] Status page green
- [ ] On-call roster published

---

## §11 — Rollback, stop, and ask-human rules

### §11.1 Per-phase rollback

- **Phase 1** (contract): revert `openapi/` to the previous tag; wake all consumers; re-run Phase 3 gate.
- **Phase 2** (data): expand/contract means **never** roll back a migration in `prod`. Roll forward with a new migration. In `dev`, `dropdb` and remigrate.
- **Phase 3–4.5** (APIs, frontends): revert the tag; keep the old schema (expand/contract).
- **Phase 5** (runner, AI): kill switches are the rollback; the code stays, the capability is disabled.
- **Phase 6** (integration/security): no rollback after the freeze without two named approvers and an incident log.
- **Phase 7** (launch): if the launch gate fails, do not launch. Fix, re-drill, re-gate.

### §11.2 Stop-and-ask triggers

A0 must stop and open `docs/OPEN_QUESTIONS.md` with tag `HUMAN_REQUIRED` if:

- Any correction marked `B` (blocker) cannot be applied as written.
- A test in Phase 3–6 fails in a way that requires a change to a frozen contract.
- Two corrections conflict.
- A decision in `OPEN_DECISIONS.md` is still `BLOCKED` at the phase gate where it is needed.
- A deviation needs to be accepted (`DV-xx`).
- Any emergency action needs a new safety rail that is not in `08 §4.12`.

Never proceed past a gate with a `HUMAN_REQUIRED` question open.

---

## §12 — Correction ledger (every R-xx, B-xx, E-xx, D-xx mapped to phase)

Populated in `docs/CORRECTIONS.md`. Each row: id, severity, phase where applied, applying agent, evidence path, status.

| ID | Sev | Phase | Agent | Where applied |
|----|-----|-------|-------|---------------|
| R-01 / D-25 | B | 0 (decision), 6 (evidence) | A0, A9 | `docs/OPEN_DECISIONS.md`, `docs/CAPACITY.md` |
| R-02 | B | 5 | A7 | Runner separate VM in prod; stub refused in prod |
| R-03 | B | 2 | A2 | Answer Pack in `gt`; role test |
| R-04 | H | 3, 4.5 | A4, A12 | Rescore on activation; not inline |
| R-05 | H | 3 | A3 | Pipeline + lock order |
| R-06 | H | 1 | A1 | Errors catalog (B3) |
| R-07 | H | 1, 3 | A1, A3 | Async upload validate |
| R-08 | H | 1, 3 | A1, A3 | `command_id` allow-list |
| R-09 | H | 1, 3 | A1, A3 | `/state` ETag + version-keyed cache |
| R-10 | H | 3 | A3 | Per-identifier login limit |
| R-11 | H | 3 | A4 | Refuse shared-secret in staging/prod |
| R-12 | M | 0, 3 | A0, A3 | Profile table |
| R-13 | M | 3, 5 | A3, A11 | Off-host backups |
| R-14 | M | 3 | A3 | `no-store` on watermarked files |
| R-15 | M | 2, 3 | A2, A3 | Idempotency retention |
| R-16 | M | 2, 3 | A2, A3 | Node-pointer sub-states |
| R-17 | M | 3 | A3 | Health/readyz/metrics; §13 hygiene |
| R-18 | M | 1, 3 | A1, A3 | `stage_key` |
| R-19 | M | 6 | A9 | Load benchmarks labeled as targets |
| R-21 | L | 0 | A0 | Reword in `skills/A0.md` |
| R-22 | M | 0 | A0 | Fix cross-reference in `skills/A4.md` |
| R-23 | M | 0, 3 | A0, A4 | Force-advance runs auto-submit first |
| R-24 | M | 5 | A7 | Same as R-02 |
| R-25 | M | 3 | A7, A8, A3 | Stubs in Phase 3 |
| R-26 | M | 0, 6 | A0, A10 | Gates reference concrete items |
| R-27 | L | 0 | A0 | Reword in `skills/A5.md` |
| R-28 | M | 3, 4 | A4, A6 | No impersonation; admin-owned preview |
| R-30 | M | 2, 3, 4.5 | A2, A4, A12 | AP requires ground_truth + step-up + two approvers |
| R-31 | M | 2, 3 | A2, A4 | `weight_multiplier` |
| R-32 | M | 2, 4.5 | A2, A12 | Overlap trigger |
| R-33 | M | 2 | A2 | Three nullable origin columns |
| R-34 | L | 4 | A6 | Numeral typed confirm |
| R-35 | M | 4 | A6 | Debug state redacts tokens |
| R-36 | L | 3, 4 | A4, A6 | Tenant scope on `/users` |
| B3 | H | 1 | A1 | Canonical error catalog |
| B4 | M | 2, 3 | A2, A3 | Idempotency retention |
| B6 | H | 3 | A3 | Pipeline + lock order |
| B7 | H | 3 | A3 | Login limits |
| B8 | H | 1, 3 | A1, A3 | `/state` cache |
| B9 | H | 1, 3 | A1, A3 | Uploads + runs |
| B10 | H | 3 | A4 | Admin auth mode gate |
| B11 | M | 2, 3 | A2, A3 | Sub-states |
| B12 | M | 1, 3 | A1, A3 | Health endpoints |
| D.1 | M | 0, 3 | A0, A3, A7, A8 | Phase 3 stubs |
| D.2 | M | 0, 3, 5 | A0, A4, A7 | Force-advance + runner VM |
| D.3 | M | 0 | A0 | Finish A8 skill, add A9–A11 |
| E.1 | H | 2, 4.5 | A2, A12 | AP tables in `gt` |
| E.2 | H | 3, 4.5 | A4, A12 | AP activation via rescore |
| E.3 | H | 4.5 | A12 | Correction protocol |
| E.4 | M | 2, 4 | A2, A6 | No impersonation, weight, tenant, numeral |

---

## §13 — Skills index (what A0 loads for each agent)

| Agent | Skill file | Additional reads (phase-specific) |
|-------|-----------|-----------------------------------|
| A0 | `skills/A0.md` | `docs/PLAN.md`, `docs/GATES.md`, `docs/CORRECTIONS.md` |
| A1 | `skills/A1.md` | `01`, `02 §6`, `docs/CONTRACTS.md`, this plan §3 |
| A2 | `skills/A2.md` | `03`, `02 §6`, this plan §4, **R-03, R-15, R-16, R-31–R-33, B4, B11, E.1** |
| A3 | `skills/A3.md` | `02 §6.1–§6.12`, **B6, B7, B8, B9, B10, B12**, `02 §13`, this plan §5 |
| A4 | `skills/A4.md` | `02 §6.13–§6.20`, **B10, E.2, E.3**, `08 Part 4`, this plan §5 |
| A5 | `skills/A5.md` | `01 §5`, `07 §5`, `07 §7`, this plan §6 |
| A6 | `skills/A6.md` | `01 §6`, `07 §6`, `08 §1`, `08 Part 4`, this plan §6 |
| A7 | `skills/A7.md` | `02 §10`, `06 §5`, **R-02/R-24**, this plan §5 and §8 |
| A8 | `skills/A8.md` | `02 §9.4`, `08 Part 3`, `06 §1`, this plan §5 and §8 |
| A9 | `skills/A9.md` | `04 §8`, `02 §12`, this plan §9 |
| A10 | `skills/A10.md` | `06 §10`, `06 §5`, this plan §9 |
| A11 | `skills/A11.md` | `05 §8`, `01 §5`, this plan §9 |
| A12 | `skills/A12.md` | `08 §2`, **E.1–E.3**, this plan §7 |
| A13 | `skills/A13.md` | `08 Part 4`, `05 §8`, this plan §7 |

---

## §14 — The five things that will kill this plan if not addressed

1. **D-25 (N) unresolved** → every capacity number is a lie, and the launch gate cannot honestly pass. Lock it before Phase 0 ends.
2. **Same-host runner in prod** (R-02) → a runner escape reaches the DB. Enforce `RUNNER_MODE=stub` refused in prod, and `RUNNER_MODE=real` on a separate VM or off.
3. **Answer Pack in `app` schema** (R-03) → the answer key leaks to participants. Enforce `gt` schema and role test as a Phase 2 gate.
4. **Inline AP scoring** (R-04/E.2) → fairness is broken for participants who already submitted. Enforce rescore-on-activation and dry-run == execute.
5. **`/state` stale across workers** (R-09/B8) → participants bounce back after submit. Enforce version-keyed cache and `ETag`, and test with 2 workers.

Each of these has a **named gate item** above. A0 does not pass the gate if any of the five is `pending`.

---

## §15 — Final note to A0

Save this file at `docs/PLAN.md`. Populate `docs/CORRECTIONS.md` from §12. Populate `docs/GATES.md` from §2.2, §3.3, §4.2, §5.4, §6.3, §7.3, §8.3, §9.4, §10.2. Copy §0.3 files into place. Copy `skills/A0.md` through `skills/A13.md` into place. Then begin Phase 0.

At every phase gate, run the gate list, write evidence to `docs/GATES.md`, and do not proceed until every item is `pass`. When in doubt, fail closed and open a `HUMAN_REQUIRED` question in `docs/OPEN_QUESTIONS.md`.

The plan is complete when `docs/GATES.md` shows every phase `pass` and `docs/CORRECTIONS.md` shows every item `applied` or `accepted_deviation` with sign-off. That is the only definition of done that matters.