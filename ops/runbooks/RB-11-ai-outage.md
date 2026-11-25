# RB-11-ai-outage: AI provider outage or budget stop

## Trigger
AI error rate > 20% over 60 s, or spend cap hit.

## Owner
Operations owner

## Steps
1. Circuit breaker opens automatically (in-process).
2. Assessments route to `NEEDS_REVIEW` — submissions NEVER wait on AI.
3. If sustained: kill switch `ai` off (banner copy from catalog).
4. Reviewers work the queue manually; AI results stay valid if already ledgered.

## Verification
- Zero submission latency impact.
- Review queue SLA still within the published schedule.

## Rollback
Switch back on; queued `ai_assess` jobs resume (stored results reused, never re-called).

