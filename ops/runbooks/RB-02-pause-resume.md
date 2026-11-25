# RB-02-pause-resume: Pause and resume the event

## Trigger
Platform fault affecting fairness (submissions failing, timing wrong, verdict leak).

## Owner
Incident commander

## Steps
1. Emergency room → pause (step-up, reason, typed confirm). Time-to-effect target ≤ 5 s.
2. Announce from the catalog: `emergency.copy.pause`.
3. Diagnose; fix via the relevant runbook.
4. Resume with `shift_deadline_by_s` = paused duration (auto-computed) unless custom.

## Verification
- Participant `/state` shows `paused: true` within 5 s of the action.
- Countdowns freeze; submit returns `STAGE_PAUSED`.
- After resume: deadlines shifted by exactly the paused window; audit shows both entries.

## Rollback
Resume (inverse action). Pause is reversible until resume.

