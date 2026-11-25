# CAPACITY.md — parametric participant count

**Rule (R-01/D-25):** the participant count is a parameter `N`. No document, comment, log,
or marketing copy may state a size that has not passed the full load profile. The supported
N is the largest size that passed; it is the only size that may be published.

## Qualification targets

| N | Status | Load profile | Qualified on | Notes |
|---|--------|--------------|--------------|-------|
| 50 | **default** | `tests/load/profile_50.py` | to_qualify (hardware TBD) | Only size that may appear in participant-facing copy |
| 100 | to_qualify | `tests/load/profile_100.py` | — | Target date: TBD |
| 200 | to_qualify | `tests/load/profile_200.py` | — | Target date: TBD |

## Load profiles (per `04 §8`)

Each profile runs through the real edge path (Caddy/compose in dev, Tunnel in prod), never localhost-only:

1. **Login burst** — N logins in 60 s (Argon2id bounded by vCPU semaphore)
2. **T0 content burst** — N participants fetch bundle/tree within 10 s of round start
3. **Steady-state polling** — N × `/state` at 12 polls/min for 10 min
4. **Submission peak** — 0.5 × N submits within 60 s at stage close
5. **Leaderboard refresh** — N reads of latest snapshot every 10 s
6. **Run burst** — 0.25 × N practice runs in 60 s (runner queue must not affect submissions)
7. **Run abuse** — 1 participant at 6 runs/min for 10 min; submissions unaffected
8. **AI scoring burst** — 200 assessments in 5 min (queue depth, latency p95)
9. **Soak** — 30 min steady state; no memory growth, no job-queue age drift
10. **DB failure + recovery** — restart Postgres under steady load; no false 200s
11. **Restore drill** — measured RTO/RPO (with A11)

## Budgets that define "pass" (from `02 §1.4`)

- Submission ack p95 ≤ 500 ms; read p95 ≤ 300 ms; `/state` p95 ≤ 250 ms at N polling
- Job queue oldest age < 5 s; zero duplicate submissions; zero lost jobs
- Error rate < 0.1 % on non-injected paths

## Recording rule

Every result records: hardware (vCPU/RAM/disk), region, image digests, script commit,
and the pass/fail table, under `docs/load/<date>-N<N>.md`. Update this file's table only
with a passing record.
