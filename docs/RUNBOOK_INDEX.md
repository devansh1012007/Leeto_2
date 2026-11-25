# RUNBOOK_INDEX.md

All runbooks live in `ops/runbooks/`. Each is one page, offline-printable, with:
trigger, owner, steps, verification, rollback. Rehearsal dates recorded in `ops/records/`.

| ID | Runbook | Trigger |
|----|---------|---------|
| RB-01 | Deploy / rollback a release | Code change needed during freeze window |
| RB-02 | Pause and resume the event | Platform fault affecting fairness |
| RB-03 | Extend a stage | Time lost to outage |
| RB-04 | Kill-switch operation | Feature misbehaving under load |
| RB-05 | Database connection exhaustion | Alerts at 70% of pool budget |
| RB-06 | Postgres restart / failover under load | DB instability |
| RB-07 | Job queue backlog | Oldest job age > 5 min |
| RB-08 | Session/token leak response | Suspected credential compromise |
| RB-09 | Runner VM rebuild | Runner compromise or VM loss |
| RB-10 | Runner kill switch + drain | Malicious run detected |
| RB-11 | AI provider outage / budget stop | AI errors > 20% or spend cap hit |
| RB-12 | Backup restore drill (quarterly + pre-event) | Scheduled; RTO/RPO measurement |
| RB-13 | Origin-direct fallback (Cloudflare outage) | Edge/Tunnel unavailable |
