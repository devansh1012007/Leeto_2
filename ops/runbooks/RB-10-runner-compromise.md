# RB-10-runner-compromise: Runner compromise response

## Trigger
Malicious run detected (escape attempt, resource abuse).

## Owner
IC

## Steps
1. Emergency room → drain_runner (no new jobs; running jobs finish) or kill_runs
   (destructive: two approvers).
2. Capture run metadata (never output content) for forensics.
3. Rebuild per RB-09.
4. Post-incident report auto-drafts at incident resolve.

## Verification
- No new runs accepted while drained.
- Run metadata preserved for the PIR.

## Rollback
kill_runs has no undo.

