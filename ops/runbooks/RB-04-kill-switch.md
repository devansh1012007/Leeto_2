# RB-04-kill-switch: Operate a kill switch

## Trigger
A feature misbehaves under load (runner queue storm, AI errors, leaderboard leaking).

## Owner
Operator

## Steps
1. Admin → switches → toggle (reason ≥ 10). Every switch is audited.
2. Verify participant copy from the catalog (`feature_disabled.<name>`).

## Verification
- Disabled endpoints return `503 MAINTENANCE` with the catalog copy within one poll cycle.
- Runner kill switch: gateway stops handing out jobs ≤ 1 s (tested).

## Rollback
Toggle back on (reason required). Existing state is never deleted by switches.

