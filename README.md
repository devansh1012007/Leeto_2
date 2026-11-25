# Bug Hunt CTF — Leeto_2

> this is a morden version of leetcode for modern ages of working with AI

Bug-hunting CTF platform: participants read planted-bug challenges, file structured bug
reports, get deterministic + AI-assisted + hidden-test scoring, on a single-VM D1 profile
(Oracle Always Free class hardware, Docker Compose, Cloudflare edge).

Execution plan: [`docs/PLAN.md`](docs/PLAN.md). Phase gates: [`docs/GATES.md`](docs/GATES.md).
Corrections ledger: [`docs/CORRECTIONS.md`](docs/CORRECTIONS.md). Capacity: parametric
`N` (default 50) — [`docs/CAPACITY.md`](docs/CAPACITY.md).

## Repository layout (T-0.1)

```
backend/
  apps/        api_participant, api_admin, worker_general, worker_evaluator,
               scheduler, runner_gateway      (FastAPI services)
  packages/    core, db, auth, events, teams, progress, drafts, submissions,
               evaluation, runs, ledger, leaderboard, review, integrity, audit,
               observability, storage, ai, runner, answer_authority, emergency
  migrations/  Alembic (expand/contract)
frontend/
  apps/        participant, admin             (Vite + React + TS)
  packages/    api-client, ui
runner/        pull-based sandboxed execution service + stub
openapi/       openapi.yaml, errors.yaml      (frozen contracts)
schemas/       JSON schemas for payloads
copy/          catalog.yaml                   (all user-visible strings)
docs/          PLAN, GATES, CONTRACTS, CORRECTIONS, CAPACITY, ... (shared memory)
skills/        A0–A13 agent skill definitions
ops/           runbooks, compose.lock, readiness
content/       rules, event details, explanations per (stage, repo option)
seeds/         dev_seed.py, synthetic_200.py
tests/         unit, integration, contract, e2e, load, security, db
tools/         lint/verify helpers
```

## Deployment profiles (B5)

| Concern | dev | staging | prod (D1) |
|---------|-----|---------|-----------|
| Frontend | Vite dev server / nginx container | nginx container | Cloudflare Pages |
| Public entry | localhost | test domain | Cloudflare Tunnel → Caddy; **no published host ports** |
| APIs | Compose services | Compose | Compose; separate Tunnel routes; admin behind Access |
| Postgres | Compose, internal network only | same | same; never on a public interface |
| Object storage | local FS | MinIO | private R2-compatible bucket; backups off-host |
| Runner | same-host container | same-host, **no real data** | **separate VM**, no internet; or **off** |
| Admin auth | shared secret allowed | Access | Access + app MFA |

**In prod, no process on the main VM executes participant-supplied code.**

## Quickstart (dev)

```bash
# 1. Backend deps
cd backend && pip install -e ".[dev]"       # or: pip install -r requirements.txt

# 2. Database (Postgres 16)
docker compose up -d postgres               # or any local Postgres
cp .env.example .env                         # adjust credentials

# 3. Migrations + roles
make migrate                                 # alembic upgrade head
make seed                                    # dev seed (< 2 s)

# 4. Run the stack
docker compose up -d                         # api_participant, api_admin, workers, scheduler, caddy
# or run individually:
uvicorn apps.api_participant.app.main:app --port 8000 --reload

# 5. Frontend
cd frontend && pnpm install && pnpm --filter participant dev   # http://localhost:5173
                                             pnpm --filter admin dev        # http://localhost:5174
```

Full stack with one command: `docker compose --profile full up --build`.

## Make targets

| Target | What it does |
|--------|--------------|
| `make lint` | ruff + mypy (boundary) + tsc |
| `make test` | pytest unit + integration |
| `make contract` | contract tests against OpenAPI |
| `make boundaries` | forbidden-import checks |
| `make migrate` | alembic upgrade head |
| `make seed` | dev seed |
| `make seed-200` | synthetic 200 participants |
| `make cold-start` | regenerate TS client + rebuild + retest |
| `make bundle-check` | participant bundle has no admin strings/secrets |

## CI

`.github/workflows/ci.yml`: lint, unit, integration (Postgres service), contract,
boundaries, openapi-lint, bundle-check, role-isolation, security-headers, cold-start,
load-smoke (from Phase 6).

## Parametric capacity rule (R-01/D-25)

Participant count is a parameter. **N=50 is the default.** N=100/200 are qualification
targets only; no doc/comment/log may state a size that has not passed the load profile
in `docs/CAPACITY.md`.

## Pushing this build to GitHub

This repository was built locally (the upstream was not cloneable from the build
environment). To publish:

```bash
git remote add origin https://github.com/devansh1012007/Leeto_2.git
git push -u origin main --force-with-lease   # first push may need --force
```
