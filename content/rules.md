# Bug Hunt CTF — Rules (version 1.0)

**Version:** 1.0 · **Last modified:** 2026-11-25 · Participants accept this version in-app
(ATH-04) with a recorded timestamp before entering any round.

## Scoring and penalties
- Each accepted finding earns points by two components: an AI assessment of your written
  report and an objective output score from hidden tests (levels 3–4). The split is
  published per level (`ai_share`).
- Time and space complexity are never scored.
- False-positive penalties apply only to reports definitively invalid after review,
  never live, and are capped per challenge.

## Ties
Total score → fewer false positives → earlier time of last accepted valid finding →
manual panel.

## Prohibited resources
External AI tools, screenshots/OCR of challenge material, sharing findings outside your
team. Watermarks allow attribution of leaked copies.

## Time and grace
The server clock is authoritative. A uniform 3-second grace window applies to everyone.
Drafts are separate from submissions.

## Appeals
Dispute window: results release + 48 hours, via the in-app dispute form.

## Platform attacks
Attacking the platform is prohibited. Safe-harbor: report vulnerabilities to the
organizer contact — no penalty for good-faith reports.

## The Run panel
Preview runs execute your code in an isolated sandbox with limits. Runs never reveal
verdicts. Attacking the runner is prohibited (see safe-harbor above).
