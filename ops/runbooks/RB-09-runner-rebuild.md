# RB-09-runner-rebuild: Rebuild the runner VM

## Trigger
Runner compromise or VM loss.

## Owner
Operations owner

## Steps
1. Kill switch: runner off (stops handouts ≤ 1 s) + drain running jobs.
2. Preserve nothing from the old VM (it held no secrets — by design).
3. Rebuild from the pinned image (ops/compose.lock digest).
4. Re-run the 8 escape tests against the new VM before re-enabling.
5. Flip the switch back on.

## Verification
- 8/8 escape tests green on the new VM.
- Submissions were unaffected the whole time (runner never blocks submit).

## Rollback
Runner stays off; scoring falls back to deterministic-only (ADR-010).

