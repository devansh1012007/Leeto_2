# RB-01-deploy-rollback: Deploy or roll back a release during the freeze window

## Trigger
A code change is required after change freeze starts (T-24h to results publication).

## Owner
Operations owner (approver: incident commander)

## Steps
1. Confirm two named approvers sign the emergency deployment (OPS-03).
2. `git tag` the current release for rollback: `git tag rollback-$(date +%s)`.
3. Build and push images with pinned digests; update `ops/compose.lock`.
4. `docker compose up -d --no-deps <service>` per affected service only.
5. Watch `/healthz`, `/readyz`, and the live console for 10 minutes.

## Verification
- `/readyz` 200 on every API (schema head, clock < 100 ms, disk ok).
- Zero new errors in the error stream for 10 minutes.
- One synthetic submit accepted end-to-end.

## Rollback
`docker compose` redeploy of the `rollback-*` tag; migrations are expand/contract only —
never roll back a migration in prod, roll forward (Phase 2 rule).

