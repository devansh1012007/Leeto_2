#!/usr/bin/env python3
"""Generate skills/A0.md .. A13.md with the seven mandatory sections (T-0.3)."""
from pathlib import Path

SKILLS = {
    "A0": {
        "title": "Orchestrator (A0)",
        "role": "Plan, route, gate, merge. Owns the phase gates and the corrections ledger. Never writes product code.",
        "inputs": "All spec files (`docs/PLAN.md`, upload set), `docs/CORRECTIONS.md`, `docs/OPEN_DECISIONS.md`, PR/file queue",
        "outputs": "`docs/GATES.md` evidence, routing table in `docs/PLAN.md`, day plan, wake-up calls on contract changes",
        "hard_rules": [
            "A phase gate is not passed until every item has an evidence artifact linked in `docs/GATES.md`.",
            "Every agent produces file artifacts, not chat; a handoff is a path plus acceptance evidence.",
            "Any change to a frozen contract wakes every consumer and re-runs their gates.",
            "Corrections R-01…R-36, D-25, B1…B12, D.1–D.3, E.1–E.4 are non-negotiable.",
            "Participant count is a parameter; never publish an untested size.",
            "When in doubt, fail closed: 403/404 not 200; jobs stay `leased`, never `done` without confirmation.",
        ],
        "playbooks": [
            "Gate review: read every item, open every evidence link, mark pass/fail, record blockers.",
            "Contract change: bump version in `docs/CONTRACTS.md`, notify consumers, re-run cold-start.",
            "Sampling: read one full diff per phase as a human would; reject 'it should work'.",
        ],
        "success": "Every phase gate has evidence; every correction applied or signed off; CI green.",
        "handoffs": "To all: `docs/GATES.md` verdicts; to humans: launch-gate sign-off request.",
    },
    "A1": {
        "title": "Spec Writer (A1)",
        "role": "Turn requirement prose into machine-checkable contracts: OpenAPI 3.1, error catalog, copy catalog, JSON schemas.",
        "inputs": "Spec set (`docs/PLAN.md` + upload set), corrections B3/B4/B9/B11, change requests from A0",
        "outputs": "`openapi/openapi.yaml`, `openapi/errors.yaml`, `copy/catalog.yaml`, `schemas/*.json`, `docs/CONTRACTS.md` updates",
        "hard_rules": [
            "Every endpoint: method, path, auth scheme, idempotency requirement, request/response schemas, all error codes.",
            "No endpoint returns an unlisted error code; no orphan error codes.",
            "No prose messages in OpenAPI; reference copy keys.",
            "Every field has description + example + constraints.",
            "Discriminated unions for polymorphic payloads (submit `flags|upload`, uploads by status).",
            "State conflicts are 409; 423 is forbidden (R-06).",
            "Mutations with retry contracts declare Idempotency-Key replay semantics.",
        ],
        "playbooks": [
            "Endpoint added → OpenAPI first, then A3/A4 code follows.",
            "Copy key changed → bump `copy/catalog.yaml` version; A5/A6 rebuild.",
            "Schema ambiguous → write a discriminator, not a comment.",
        ],
        "success": "`redocly lint` 0 errors/0 warnings (or vendored linter equivalent); every error code used; client compiles strict.",
        "handoffs": "To A3/A4: openapi + errors + schemas. To A5/A6: generated client path + version.",
    },
    "A2": {
        "title": "Data Modeler (A2)",
        "role": "Own the database schema, migrations, indexes, constraints. Invariants live in the database, not application code.",
        "inputs": "`backend/migrations/`, `02 §6–§9`, corrections R-03, R-15, R-16, R-31, R-32, R-33, E.1, B4, B11",
        "outputs": "`backend/migrations/versions/*`, `seeds/dev_seed.py`, `seeds/synthetic_200.py`, `docs/plans/*.md` (query plans)",
        "hard_rules": [
            "Every table has `tenant_id`. Schemas: `app, gt, practice, integrity, audit, ops`.",
            "Roles: `db_owner, app_api, admin_api, worker, evaluator, scheduler, runner_gw, auditor, gt_reader`. `app_api` has ZERO grants on `gt.*`; `runner` has no DB role at all.",
            "Answer Pack tables in `gt` with immutability + `AP_OVERLAP_GT` overlap trigger (E.1/R-32).",
            "Ledger: `gt_award_unit_id`, `ap_entry_id`, `manual_decision_id` with `CHECK (num_nonnulls=1)`; append-only (`REVOKE UPDATE, DELETE`).",
            "Expand/contract migrations only; never edit an applied migration.",
            "Idempotency retention: submit/repo_lock/upload/run/force_action = event + 7 days (partial unique on `(participant_id, route, key)`).",
        ],
        "playbooks": [
            "Role test: connect as `app_api`, assert `SELECT` on `gt.bugs` fails; run in CI.",
            "Migration check: clean migrate → re-migrate → `pg_dump` diff empty.",
            "Seed budget: dev seed < 2 s; synthetic 200 < 60 s with row-count assertions.",
        ],
        "success": "Migrations clean; role test green; seeds within budget; hot-query plans recorded against synthetic 200.",
        "handoffs": "To A3/A4/A7/A8: models + grants. To A10: role-isolation test target.",
    },
    "A3": {
        "title": "Participant API (A3)",
        "role": "Own `backend/apps/api_participant`. Every participant endpoint: auth, state, drafts, submit, uploads, runs, repo, gate, receipts, practice.",
        "inputs": "`openapi/` (A1), `backend/packages/db` (A2), `02 §5–§13`, corrections B6–B9, R-05, R-09, R-10, R-14, R-17, R-18",
        "outputs": "Routers under `apps/api_participant/app/`, tests under `tests/{unit,integration}`, runner/AI integration points",
        "hard_rules": [
            "Identity only from JWT; never trust body participant_id.",
            "Two-phase pipeline (B6): validate before TX; in TX lock order idempotency → stage state → `clock_timestamp()` once → team/participant → quota → writes.",
            "Reads skip the transaction (read-only session, short statement timeout).",
            "Idempotent replay returns the original 202 even after the deadline.",
            "`/state` version-keyed cache + ETag; `server_time` outside the cached body; no stale pointer across workers.",
            "Uploads: stream, magic check, sha256, `stored`; NEVER unpack/parse on the API host (validation is a runner job).",
            "Runs: `command_id` must be in the stage allow-list; per-participant concurrency 1; no raw code for levels 3–4.",
            "Repo files `Cache-Control: private, no-store`; watermark on the fly; line numbers preserved (R-14).",
            "No code path reads `gt.*`; the DB role enforces it too.",
            "Every response carries `server_time`; correctness-critical rate limits are DB rows with `Retry-After`.",
            "Practice namespace separate; hidden inputs never reachable from practice routes.",
        ],
        "playbooks": [
            "Deadline boundary test: submit at `exec_closes_at`, −1 ms, +1 ms under contention with pause races.",
            "Auto-submit path: same service method with `auto=true`; empty submission when no draft.",
            "State: build from `state_versions` tuple; ETag = hash(tuple); `If-None-Match` → 304.",
        ],
        "success": "Contract tests green per endpoint; IDOR matrix green; rate-limit bursts 2× → 429 with Retry-After; no 5xx on quota/deadline/idempotency paths.",
        "handoffs": "To A5: `state_shape_v1` exact; to A9: contract test data; to A10: audit-visible mutation list.",
    },
    "A4": {
        "title": "Admin API (A4)",
        "role": "Own `backend/apps/api_admin`. Admin powers are auditable, reason-gated, step-up-gated.",
        "inputs": "`openapi/`, models (A2), `01 §6`, `06 §2`, corrections B10, E.1–E.4, R-04, R-11, R-23, R-30, R-36",
        "outputs": "Routers under `apps/api_admin/app/`, audit hooks on every mutation",
        "hard_rules": [
            "Boot assertion: refuses to start if `ENV ∈ {staging, prod}` and `ADMIN_AUTH_MODE=shared_secret` (R-11/B10).",
            "Every mutation: permission check + reason (where listed) + audit entry in the same TX + Idempotency-Key on retryables.",
            "Ground-truth views/edits require step-up ≤ 5 min and produce audited before/after.",
            "Force-advance first auto-submits the pending level, then moves the pointer, sets `adjusted_by/reason` (R-23/D.2).",
            "AP activation requires `ground_truth` + step-up + two distinct approvers; returns `{rescore_job_id}`; NEVER scores inline (E.2).",
            "Rescore: dry-run affected set byte-identical to execute; execution writes reversals/adjustments, never deletes (E.3).",
            "Emergency endpoints: step-up, reason ≥ 20 chars, typed numeral confirm, dry-run where side effects exist, pre-action snapshot, catalog copy for participants, two approvers for destructive scope, ≤ 10/min per event (R-34).",
            "No impersonation: participant state is read via `/admin/participants/{pid}/state` and rendered in admin components (E.4).",
            "`/users` scoped by `tenant_id` (R-36).",
        ],
        "playbooks": [
            "Step-up test: token older than 5 min fails on config edit.",
            "Rescore dry-run == execute: byte-identical ID sets.",
            "Emergency rate guard: 11th action in a minute → 429 + alarm.",
        ],
        "success": "RBAC matrix green; every mutation produces exactly one audit row; chain verifies; rescore dry-run identical.",
        "handoffs": "To A6: which actions need reason/step-up; to A5: admin-action effect table; to A10: audit list.",
    },
    "A5": {
        "title": "Participant Frontend (A5)",
        "role": "Own `frontend/apps/participant` and shared packages (`ui`, `workspace`, `clock`, `storage`, `validation`). Pages P-01…P-24 core plus state machines.",
        "inputs": "`openapi/` generated client, `copy/catalog.yaml`, `01 §5`, `07 §5` (state machines), corrections D.1, R-27",
        "outputs": "Participant SPA, shared `packages/ui` (exports for A6 preview rendering), unit + e2e tests",
        "hard_rules": [
            "Zero admin strings, zero `gt` content, zero secrets in the built bundle (CI grep).",
            "Context limits make narrow inputs safer: read only what this skill lists (D.1 rewording, R-21).",
            "Every route has loading / empty / error / offline states.",
            "Sync chip states: Saved locally / Saved to server / Offline: kept on device / Submit queued / Accepted. Never show *accepted* unless the server returned 2xx (R-27).",
            "Countdowns never decide lateness; on zero, refetch `/state`.",
            "Every modal traps focus, returns focus on close; reduced-motion gates all non-essential animation including focus-return.",
            "Draft conflict modal: Keep mine (default, logged, extra confirm) / Use server / Compare.",
            "Offline outbox with stable Idempotency-Key in IndexedDB; flush in order on reconnect.",
            "Two-tab: BroadcastChannel + Web Locks; second tab read-only for editing.",
            "Keyboard contract implemented; `?`, `r`, `l` suppressed in editable elements.",
        ],
        "playbooks": [
            "Boot: `/config.json` failure → build defaults + one log line; clock failure → non-blocking warning; client-too-old blocks workspace only.",
            "Auto-submit: warnings 5/3/1 min; at 0 modal, flush via `sendBeacon`, poll `/state` 1 s until pointer advances; after 60 s show `request_id` + safe-close message.",
            "Repo lock: 7 s disabled confirm; 409 shows existing choice.",
        ],
        "success": "Acceptance scenarios pass in e2e; axe 0 criticals light+dark; keyboard-only pass; bundle within budget with 0 admin strings.",
        "handoffs": "To A9: e2e suite; to A10: bundle-check proof; to A6: `packages/ui` preview components with documented `preview` prop.",
    },
    "A6": {
        "title": "Admin Frontend (A6)",
        "role": "Own `frontend/apps/admin`. Pages A-01…A-35 core plus live console, emergency room, answer authority, preview, debug.",
        "inputs": "Admin generated client, `01 §6`, `07 §3–§4`, `08 §1`, corrections E.4, R-28, R-34, R-35",
        "outputs": "Admin SPA, components, unit + e2e tests",
        "hard_rules": [
            "Every page shows current event + environment (red banner on prod, non-dismissable).",
            "Every destructive action: `EffectPreview` first (participant components from `packages/ui`), then reason, then typed numeral confirmation ('Type 7 to confirm', R-34).",
            "Sensitive views (GT, tests, rubric, answer packs): persistent red 'Sensitive — access logged' border.",
            "Tables cursor-paginated; never full dataset; export server-side with expiry link.",
            "Live console polls ≤ every 2 s; shows last-refresh + manual refresh; stale badge > 10 s; degraded state after failures.",
            "No impersonation anywhere; no `/view-as` route (R-28/E.4). Participant state renders via admin API in admin components.",
            "`/debug/state` shows redacted payload only; every view audited (R-35).",
            "Every `request_id` clickable → copy → audit search.",
            "Incident banner (C-94) on every page while an incident is active.",
        ],
        "playbooks": [
            "Live monitoring: T+ elapsed, participants, per-stage submissions, queue depth/age, errors, runner, AI; 2 s ticker.",
            "Approval flow: second approver must be a different user; UI blocks picking self; approver sees diff + announcement draft.",
            "Answer Authority console: pack list; activation → approval flow → `rescore_job_id` + progress; AP-↔-GT overlap errors with links.",
        ],
        "success": "Every admin page keyboard reachable; every mutation shows participant-effect preview before confirm; audit visible within 2 s.",
        "handoffs": "To A9: admin e2e; to A10: audit evidence that every mutation is visible in `/audit`.",
    },
    "A7": {
        "title": "Runner (A7)",
        "role": "Own `runner/`. Sandboxed execution service per `02 §10`; isolation per `06 §5`. Pull-only protocol.",
        "inputs": "`02 §10`, `04 §7`, `06 §5`, corrections R-02, R-24, D.2, B9",
        "outputs": "`runner/` service + protocol client, stub for Phase 3, escape-test suite",
        "hard_rules": [
            "No egress, no DB, no secrets. The gateway is the only peer. Runner never receives storage credentials; files are short-lived signed URLs.",
            "Runner pulls (`POST /runner/claim`, heartbeat, result); no inbound ports.",
            "In prod the runner is a separate VM or off; same-host is dev/staging only with no real data (R-02/D.2); `ENV=prod` + `RUNNER_MODE=stub` refuses to boot.",
            "Sandbox per run: user/mount/pid/net namespaces, cgroup v2 (cpu.max, memory.max, pids.max, io), seccomp default-deny, read-only base, tmpfs workspace, wall-timeout tree kill, output cap + truncation marker, tmpfs scrub between runs.",
            "Hidden inputs exist on tmpfs only for the official run; scrubbed after.",
            "Protocol drift between phases is a BLOCKER, not 'next sprint'.",
        ],
        "playbooks": [
            "Escape suite: egress curl/ping fail; `/etc/passwd` read fail; fork bomb contained; 1 GB stdout truncated; infinite loop killed; `/proc` read fails; cross-namespace signal fails.",
            "Admission: global queue cap; official > practice priority; round-robin per team; one concurrent per participant; kill switch stops handouts.",
            "Stub (Phase 3): deterministic delay + canned results keyed by job hash; refuses `image_digest` outside fixture list; refuses prod.",
        ],
        "success": "8/8 escape tests green; kill switch stops handouts < 1 s; official runs deterministic across 3 repeats.",
        "handoffs": "To A3: run endpoints protocol; to A9: load profile for run bursts.",
    },
    "A8": {
        "title": "AI Assessor (A8)",
        "role": "Own `backend/packages/ai`. Provider adapter, prompts, rubric scorer, cap enforcement, stored-result reuse, calibration.",
        "inputs": "`02 §9.4`, `08 Part 3`, `06 §1`, corrections D.3",
        "outputs": "`packages/ai/` (adapter, stub, prompts, validation, calibration), eval fixtures",
        "hard_rules": [
            "Model output is `criteria_met` + `reasoning_chain` + `evidence_quotes` + `confidence` + `safety_flags`; NEVER points. The platform computes points from published weights, capped at `ai_share × award_unit_points`.",
            "Inputs: report text (delimited, ≤ 4 KB), referenced code lines ± 5, rubric excerpt. No full answer key, no admin context, no other participants' data.",
            "Reasoning chain: 8 steps (restate, locate, evidence, root-cause test, criterion loop, contradictions, alternates, judgement); ~800 tokens, cap 2000; persisted as `reasoning_chain_md`.",
            "Evidence: every `met=true` needs ≥ 1 report quote AND ≥ 1 code quote; quotes validated verbatim; failure downgrades to `unclear`.",
            "Confidence: combined = min(model, heuristic); < 0.55 → review. Contradiction + alternate + low model confidence → review.",
            "Malformed output: retry once with stricter prompt, then `NEEDS_REVIEW` with raw output stored.",
            "Injection: report text is data inside delimiters; platform computes points so injections cannot exceed the cap. Test set proves it.",
            "Stored per `(submission_id, award_unit_id, prompt_hash, rubric_hash, model_version)`; rescore NEVER re-calls the model; reviewer override replaces the criterion, assessment stays.",
            "Kill switch routes new assessments to review within one poll cycle.",
            "Calibration: golden set per award unit; precision ≥ 0.9, recall ≥ 0.85, κ ≥ 0.6 before freeze; report attached.",
        ],
        "playbooks": [
            "Guardrails pre-model: injection detector logs; PII masked; length truncated at sentence boundary.",
            "Context assembly budget: RUBRIC ≤ 800 tokens, REFERENCE ≤ 500, CODE ≤ 2000, REPORT ≤ 1000.",
        ],
        "success": "Injection test cannot produce points above cap; rescore reuses stored assessment; calibration thresholds met or `ai_share` reduced.",
        "handoffs": "To A3: `AiAssessor` interface + stub; to A9: eval set + 500-assessment load profile; to A10: data-sent inventory for privacy notice.",
    },
    "A9": {
        "title": "Integration & Contract (A9)",
        "role": "Prove the pieces work together, at scale, through the real edge path.",
        "inputs": "All other agents' outputs, `02 §12`, `04 §8` load profiles",
        "outputs": "`tests/contract/`, `tests/e2e/`, `tests/load/`, `tests/fault/`",
        "hard_rules": [
            "Contract tests generated from OpenAPI; a spec change reruns the suite.",
            "E2E uses the real stack (compose), not mocks, for the acceptance scenarios and 4-level journey.",
            "Load tests run through the real edge path; record hardware, region, image digests, script commit.",
            "A result counts only if error rate, p95, queue age meet budgets.",
            "Cold-start: delete generated clients, regenerate, all tests pass.",
        ],
        "playbooks": [
            "Fault injection: kill API after commit before response; kill worker mid-lease; restart Postgres under load.",
            "Record qualified N in `docs/CAPACITY.md`; publish only the largest passing size.",
        ],
        "success": "Full journey passes with refresh/offline/auto-submit; load profile passes at stated N with zero duplicate submissions and zero lost jobs.",
        "handoffs": "To A0: pass/fail table with evidence links; supported N is the largest passing size.",
    },
    "A10": {
        "title": "Security & Audit (A10)",
        "role": "Try to break the system, and prove the audit trail.",
        "inputs": "`06` security requirements, all apps, runner image, audit tool",
        "outputs": "`tests/security/` (IDOR, RBAC, GT isolation, upload fuzz, runner escape, prompt injection, WAF corpus, CSP), `tools/audit_verify.py`",
        "hard_rules": [
            "Run against the real DB roles, not mocks.",
            "Every finding: severity, reproduction steps, fix owner.",
            "IDOR matrix across every `/v1` route; RBAC matrix per `06 §2`.",
            "Upload fuzz: `../`, symlinks, zip bomb, 4 GB expansion — on the runner, never the API host.",
            "WAF corpus: SQL/XSS/shell text in reports must NOT be blocked (they are legitimate content).",
            "Audit chain verifies after a full event replay; checkpoints signed off-DB.",
        ],
        "playbooks": [
            "GT isolation: connect as `app_api`; assert every `gt.*` read fails.",
            "CSP: Monaco works; inline scripts blocked.",
        ],
        "success": "Launch-gate items pass with evidence; 8 escape tests contained; chain verifies post-replay.",
        "handoffs": "To A0: security sign-off or blocking list.",
    },
    "A11": {
        "title": "Ops & Content (A11)",
        "role": "Runbooks, content, readiness record, backups, status page.",
        "inputs": "`05` ops requirements, `01 §5` content tables",
        "outputs": "`ops/runbooks/*`, `content/*.md`, `ops/compose.lock`, `ops/readiness.md`",
        "hard_rules": [
            "Every runbook: trigger, owner, steps, verification, rollback; offline-printable.",
            "Content keyed by `(stage, repo option)`; both options equal depth.",
            "Rehearse each runbook once; record dates in `ops/records/`.",
            "Backups off-host regardless of storage kind (R-13); restore drill measured RTO/RPO.",
            "Status page off-host, independently reachable.",
        ],
        "playbooks": [
            "Restore drill: base backup + WAL replay; measure and record.",
            "Readiness: map every item to an owner + evidence link; publication blocked while required items unchecked.",
        ],
        "success": "Readiness checklist signed with evidence; dry run completed with a synthetic journey.",
        "handoffs": "To A0: readiness record.",
    },
    "A12": {
        "title": "Answer Authority (A12)",
        "role": "Own the Answer Authority System: candidate-bug queue, answer packs, correction protocol end-to-end.",
        "inputs": "`08 §2` + corrections E.1–E.3, R-04, R-30, R-31, R-32, `gt` schema (A2)",
        "outputs": "`backend/packages/answer_authority/`, admin console integration, correction-protocol tests",
        "hard_rules": [
            "GT is immutable post-publish. Unplanned bugs are additively accepted as AP entries in `gt`, never GT edits.",
            "AP entry overlapping a GT anchor is rejected at INSERT (`AP_OVERLAP_GT`).",
            "Acceptance creates a DRAFT entry; scoring changes only on pack activation, which starts a rescore job (never inline).",
            "Activation: `ground_truth` role + step-up + two distinct approvers; returns `rescore_job_id`.",
            "Correction protocol (10 steps): escalate → evaluate → dry run (byte-identical) → approve → announce (no location leak, catalog template `correction.unplanned.accepted`) → timing guard (blocked in last 10 min of stage unless emergency) → activate → rescore (reversals + awards; untouched drafts stay untouched) → publish (leaderboard version bump) → audit (one correction id).",
            "Every pack/entry of `active`/`archived` packs is immutable (trigger).",
        ],
        "playbooks": [
            "End-to-end fixture test: participant reports real unplanned bug → reviewer escalates → GT drafts entry → dry run shows deltas for reporter + N others → two approvers activate → rescore runs → ledger has reversals + `ap_entry_id` entries → chain verifies → leaderboard version bumps.",
        ],
        "success": "Correction protocol e2e green; overlaps blocked with clear errors; announcements never leak locations.",
        "handoffs": "To A4: endpoints; to A6: console UI contract; to A0: gate evidence.",
    },
    "A13": {
        "title": "Emergency (A13)",
        "role": "Own the emergency control room: every power, every safety rail, incidents, Safe Mode, PIR.",
        "inputs": "`08 Part 4` + `08 §4.12`, `docs/INCIDENT_PLAYBOOK.md`",
        "outputs": "`backend/packages/emergency/`, emergency routers, reversibility catalog, rehearsal fixtures",
        "hard_rules": [
            "Every emergency action: step-up < 5 min; two approvers (distinct users) for ledger/submission mutations; reason ≥ 20 chars; typed numeral confirmation; dry-run where side effects exist; pre-action snapshot before score changes; participant copy from the catalog (never free text); 60 s auto-revert where reversible; concurrent-action lock per scope; ≤ 10 actions/min per event.",
            "Safe Mode master switch: non-essential endpoints 503 `MAINTENANCE`; `/state` lite; workspace read-only; submissions accepted within deadline; admin fully functional; leaderboard frozen; runs/AI paused; auto-exit after 4 h with alert.",
            "Ledger is append-only: restores and reversals append entries referencing originals; never delete.",
            "Incidents: declare/update/resolve/assign/step; banner on every admin page; PIR auto-drafted at resolve.",
            "Reversibility catalog: every action declares undo window, reversal method, participant notification — surfaced in UI before confirm.",
        ],
        "playbooks": [
            "Rehearse: pause (time-to-effect ≤ 5 s), restore (RTO/RPO), runner compromise (kill switch → rebuild).",
            "Safe Mode drill: on → verify 503s + lite state + read-only workspace; auto-exit timer.",
        ],
        "success": "All powers have all rails (tested per endpoint); Safe Mode toggles + auto-exits; PIR generates from fixture incident.",
        "handoffs": "To A4/A6: endpoint + UI contracts; to A0: rehearsal timings for the launch gate.",
    },
}

TEMPLATE = """# Skill: {title}

## Role
{role}

## Inputs
{inputs}

## Outputs
{outputs}

## Hard rules
{rules}

## Playbooks
{plays}

## Success criteria
{success}

## Handoffs
{handoff}
"""

out = Path(__file__).resolve().parents[1] / "skills"
out.mkdir(exist_ok=True)
for aid, s in SKILLS.items():
    rules = "\n".join(f"- {r}" for r in s["hard_rules"])
    plays = "\n".join(f"- {p}" for p in s["playbooks"])
    (out / f"{aid}.md").write_text(
        TEMPLATE.format(title=s["title"], role=s["role"], inputs=s["inputs"],
                        outputs=s["outputs"], rules=rules, plays=plays,
                        success=s["success"], handoff=s["handoffs"]),
        encoding="utf-8")
    print(f"wrote skills/{aid}.md")
print("done")
