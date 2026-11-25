# CONTRACTS.md — frozen contract index

Watched file set: `openapi/openapi.yaml`, `openapi/errors.yaml`, `copy/catalog.yaml`,
this file, `03_Database_Spec` equivalents (`backend/migrations/`), `docs/CORRECTIONS.md`.
Any change here wakes the consumers listed for that entry and re-runs their gates.

## Endpoint groups

| Group | Endpoints | Producer | Consumers | Lock status |
|-------|-----------|----------|-----------|-------------|
| auth (`/auth/*`, `/me`) | login, refresh, logout, activate, reset, me | A3 | A5, A6, A9 | frozen v1 |
| consent (`/consent`) | get, accept | A3 | A5 | frozen v1 |
| public event (`/event/public`, `/content/event-details`, `/time`) | reads | A3 | A5 | frozen v1 |
| state & progress (`/state`, `/progress`, `/leaderboard`, `/team*`, `/announcements`) | reads | A3 | A5, A9 | frozen v1 (state_shape_v1) |
| repo (`/repo/*`) | tree, files, search, symbol | A3 | A5 | frozen v1 |
| repo lock (`/team/repo-lock`) | get, post | A3 | A5 | frozen v1 |
| gate (`/stages/{key}/gate`) | get | A3 | A5 | frozen v1 |
| drafts (`/drafts/{stage_key}`) | get, put | A3 | A5 | frozen v1 |
| submit (`/stages/{key}/submit`) | post | A3 | A5, A9 | frozen v1 |
| uploads (`/uploads*`) | post, validate, get, delete | A3 | A5, A7 | frozen v1 |
| runs (`/runs*`) | post, get, cancel | A3 (A7 protocol) | A5, A7 | frozen v1 |
| receipts & results (`/receipts/{id}`, `/results`, `/disputes`) | reads, dispute post | A3 | A5 | frozen v1 |
| practice (`/practice/*`) | mirror of workspace reads | A3 | A5 | frozen v1 |
| ops (`/healthz`, `/readyz`, `/metrics`) | internal reads | A3/A4 | A9, A11 | frozen v1 |
| admin auth (`/admin/auth/*`) | step-up, logout | A4 | A6 | frozen v1 |
| admin events/stages/content (`/admin/events*`) | CRUD + lifecycle | A4 | A6 | frozen v1 |
| admin participants/teams (`/admin/events/{id}/participants*`, `/admin/users*`) | CRUD, import, actions | A4 | A6 | frozen v1 |
| admin challenges & GT (`/admin/challenges*`) | CRUD, freeze, seal | A4 | A6, A12 | frozen v1 |
| admin live ops (`/admin/events/{id}/live*`, pause/resume/extend/switches/announcements) | reads + mutations | A4 | A6 | frozen v1 |
| review & disputes (`/admin/review*`, `/admin/disputes*`) | queue, decide | A4 | A6 | frozen v1 |
| rescore & finalize (`/admin/events/{id}/rescore*`, leaderboard mode, finalize) | dry-run, execute | A4 | A6, A12 | frozen v1 |
| answer authority (`/admin/challenges/{id}/answer-packs*`, candidate-bugs) | packs, entries, links, activate | A4 | A6, A12 | frozen v1 |
| emergency (`/admin/.../emergency/*`, `/admin/incidents*`) | powers with safety rails | A4 | A6, A13 | frozen v1 |
| admin audit/exports/health (`/admin/audit*`, `/admin/exports*`, `/admin/health`) | reads | A4 | A6, A10 | frozen v1 |
| runner protocol (`/runner/claim`, `/runner/jobs/{id}/heartbeat|result`) | runner→gateway | A7 (gateway: A3 side) | A7 | frozen v1 |

## `state_shape_v1` (additive-only; version bump + wake A5/A6/A9 on any change)

```
{
  "server_time": iso8601 (NOT part of the ETag body),
  "event": { "id": uuid, "status": draft|published|live|ended|archived, "paused": bool,
             "tz": string, "maintenance": bool, "safe_mode": bool },
  "me": { "participant_id": uuid, "team_id": uuid|null, "role": string,
          "consent_required": bool, "min_client_version": string },
  "node_pointer": { "node": enum, "sub_state": enum, "version": int, "adjusted_by": uuid|null },
  "stages": [ { "stage_key": slug, "ordinal": int, "name": string, "kind": explain_only|flags|upload,
                "explain_opens_at": ts, "exec_opens_at": ts, "exec_closes_at": ts,
                "state": locked|open|closed, "paused": bool,
                "submitted": bool, "gate": { "allowed": bool, "waiting_on": [string] } } ],
  "team": { "score": number, "score_version": int, "repo_choice": string|null },
  "versions": { "progress_version": int, "score_version": int, "leaderboard_version": int,
                "flags_version": int, "announcement_version": int },
  "announcements": [ { "id": uuid, "severity": info|warn|critical, "body_md": string,
                       "created_at": ts } ],   // latest 5, full list via /announcements
  "feature_flags": { "leaderboard": bool, "runner": bool, "ai": bool, "uploads": bool,
                     "announcements": bool, "practice": bool, "read_only": bool }
}
```

- `ETag` = sha256 of the version tuple `(progress_version, score_version, leaderboard_version, flags_version, announcement_version)`.
- `If-None-Match` → `304` with empty body.
- `server_time` is added outside the cached body and is always fresh.

## Frozen patterns

- **`stage_key`**: `^[a-z0-9_]{3,32}$`, unique per event. `ordinal` is informational only.
- **`command_id`**: `^[a-z][a-z0-9_]{2,32}$`; stage config (`run_commands`) declares the allow-list with fixed argv, env, timeout, resource class. Participants never send argv.
- **Upload lifecycle**: `stored → validating → ok | failed`. Submit requires `ok` (or `validation=deferred` when runner is down, with documented grace).
- **Node-pointer sub-states** (B11): base nodes `LANDING, L1_EXPLAIN, L1_EXEC, L1_SUBMITTED, …, DONE`; sub-states `waiting_repo_lock, ready, active, submitting, evaluating, evaluated, adjusted`. Forward-only on `(stage, node)`.
- **Error envelope**: `{ "error": { "code", "message", "details"?, "request_id" } }`; success: `{ "data": …, "meta": { "request_id", "server_time" } }`.
- **Idempotency**: opaque key 8–128 chars, scoped `(participant_id, route, key)`; same payload hash → original response replay (even after deadline); different hash → `409 IDEMPOTENCY_CONFLICT`. Retention: submit/repo_lock/upload/run/force_action = event + 7 days; others 24 h.
- **Ledger origins** (E.1/R-33): `gt_award_unit_id`, `ap_entry_id`, `manual_decision_id` — exactly one non-null.
- **Time**: all decisions use `clock_timestamp()` read once after the stage-state lock; PostgreSQL is the deadline authority.
