# RB-07-job-backlog: Job queue backlog

## Trigger
Oldest job age > 5 min (budget: < 5 s).

## Owner
Operations owner

## Steps
1. Live console → queue depth/age; identify the kind.
2. If evaluator: check worker_evaluator logs and gt read latency.
3. If outbox: check SMTP provider (RB-11 pattern).
4. Dead-lettered jobs: inspect `app.jobs` state='dead', fix cause, re-enqueue with new dedupe key.

## Verification
- Queue age < 5 s for 10 minutes.

## Rollback
n/a.

