# RB-03-extend-stage: Extend a stage after an outage

## Trigger
Time lost to a platform outage.

## Owner
Organizer + IC

## Steps
1. Compute lost time from the incident timeline.
2. Admin → stage → extend {minutes, reason ≥ 10}.
3. Announcement goes out automatically (catalog copy with {minutes}).

## Verification
- Countdown jumps by N minutes on next poll (≤ 5 s).
- Auto-submit jobs rescheduled; subsequent stage open times shifted.
- Undo window 60 s via the emergency action toast.

## Rollback
60 s undo, or inverse extend with negative… not available: use pause+resume instead.

