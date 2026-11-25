# RB-12-restore-drill: Backup restore drill (quarterly + pre-event)

## Trigger
Scheduled (pre-event mandatory; readiness gate item).

## Owner
Operations owner + A11

## Steps
1. Take the latest base backup + WAL archive (off-host — R-13).
2. Restore to a scratch VM: fresh Postgres, replay WAL to a target time.
3. Measure: RTO (start → serving reads), RPO (last committed transaction present).
4. Run the audit chain verifier against the restored DB (`tools/audit_verify.py`).
5. Record RTO/RPO + date in `ops/records/restore-drills.md`.

## Verification
- App boots against the restored DB; `/readyz` 200.
- Audit chain verifies end-to-end.
- Results recorded and signed.

## Rollback
n/a (drill).

