# RB-05-db-connections: Database connection exhaustion

## Trigger
Alert at 70% of the planned connection budget (03 §8 pool plan: max 74 of 120).

## Owner
Operations owner

## Steps
1. `SELECT count(*) FROM pg_stat_activity` grouped by usename.
2. Identify the pool leaking (usually a stuck transaction holding a connection).
3. `SELECT pg_terminate_backend(pid)` for idle-in-transaction > 5 min.
4. Scale that service's pool down or restart the service (graceful: drains 30 s).

## Verification
- pg_stat_activity back under 70%.
- No `UPSTREAM_UNAVAILABLE` errors in the stream.

## Rollback
Pool sizing returns to `04 §6` plan values; alert clears.

