# RB-06-db-restart: Restart Postgres under load

## Trigger
DB instability (corruption signals, OOM, provider maintenance).

## Owner
Operations owner

## Steps
1. Expect: in-flight transactions roll back — NO false 200s (fail-closed by design).
2. `docker compose restart postgres` (or VM-equivalent).
3. APIs return `503 UPSTREAM_UNAVAILABLE` during the window; clients retry with backoff.
4. On recovery, verify job leases: reaper (JOB-15) reclaims expired leases within 30 s.

## Verification
- Zero acknowledged submissions lost (idempotency + receipts).
- Job queue drains; oldest-job age < 5 s within 2 minutes.

## Rollback
n/a (restart is the action). Escalate to RB-12 if data recovery is needed.

