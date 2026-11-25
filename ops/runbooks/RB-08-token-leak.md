# RB-08-token-leak: Suspected credential leak

## Trigger
Token/session compromise suspicion.

## Owner
IC + security owner

## Steps
1. Emergency room → kill_sessions for the account (reversible) or logout_all (destructive,
   two approvers + typed confirm).
2. Rotate `JWT_SECRET` (forces full re-auth; requires RB-01 deploy window).
3. Audit: every view of the affected participant state is logged.

## Verification
- Affected sessions return `AUTH_SESSION_EXPIRED`.
- No new sessions from leaked tokens (rotate verified by 401 rate spike then normal).

## Rollback
logout_all has no undo (typed 'LOGOUT ALL' — extremely disruptive).

