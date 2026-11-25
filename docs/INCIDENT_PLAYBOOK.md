# INCIDENT_PLAYBOOK.md

How to run the launch rehearsal and live incidents. Companion to `ops/runbooks/`.

## Roles (named on A-33 before the event)

- **Incident commander (IC)** — one person decides; others execute.
- **Communications owner** — participant banner, status page, email.
- **Operations owner** — executes runbooks, kill switches, restores.

## Incident lifecycle

1. **Declare** — `POST /admin/incidents {severity}` → banner on all admin pages.
2. **Stabilize** — Safe Mode (`/admin/events/{id}/emergency/safe-mode`) if blast radius must shrink.
3. **Diagnose** — live console (`/events/{id}/live`): queue age, error stream, runner/AI health.
4. **Repair** — runbook from `ops/runbooks/`; record steps via `/admin/incidents/{id}/step`.
5. **Communicate** — announcement from copy catalog (never free text) at declare, fix, resolve.
6. **Resolve & PIR** — auto-drafted post-incident report; IC reviews and attaches to archive.

## Rehearsal scenarios (Phase 7)

| Scenario | Runbook | Measured |
|----------|---------|----------|
| Pause/resume | RB-02 | time-to-effect for all participants (target ≤ 5 s) |
| Restore | RB-12 | RTO/RPO vs drill target |
| Runner compromise | RB-10 | kill-switch → rebuilt runner time |
| DB restart under load | RB-06 | no false 200s; recovery time |
| Token leak suspicion | RB-08 | logout-all time-to-effect |

## Non-negotiables during an incident

- Ledger and audit are append-only; recovery writes reversals, never deletes.
- Emergency actions: step-up < 5 min, reason ≥ 20 chars, typed confirmation, two approvers for destructive scope, pre-action snapshot, ≤ 10 actions/min.
- If authorization cannot be determined on a path, fail closed (403/404, never 200).
- If a background job cannot confirm completion, it stays `leased`, never `done`.
