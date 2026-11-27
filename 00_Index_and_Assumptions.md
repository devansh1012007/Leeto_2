# Bug Hunt CTF: Full Specification Set

**Version:** 0.1 draft · **Profile:** D1 (student/free MVP) with the optional runner and AI assessment · **Audience:** the whole build team

This set specifies the whole system: pages, components, backend, database, network, I/O, compute, deployment, operations, security and the things nobody has asked about yet. It builds on, and must stay consistent with:

- `Bug_Hunt_CTF___System_Architecture.md` (v2.2, **authority** on conflicts)
- `03-specification.md` (v2 requirements and API conventions)
- `01_blind-spots-and-cautions.md` (risk register)
- `Bug_Hunt_CTF_Participant_Website_Spec.md` (the four-level event flow)

If this set contradicts the architecture, the architecture wins until an ADR changes it. Where this set **needs** the architecture to change, it says so in a *Conflict* note and in §6 of the participant website spec.

---

## 1. Document map

| File | Covers |
|------|--------|
| `00_Index_and_Assumptions.md` | This file: map, ID scheme, assumptions, invariants, glossary, decision list |
| `01_Frontend_Spec.md` | Tech stack, global behavior, design tokens, component catalog, every participant page, every admin page |
| `02_Backend_Spec.md` | Services, modules, conventions, full API catalog, payloads, state machines, jobs, evaluator, AI, runner protocol |
| `03_Database_Spec.md` | Roles and grants, every table, constraints, indexes, retention, sizing, hot queries |
| `04_Network_IO_Compute_Spec.md` | Network topology, timeouts, bandwidth, disk I/O, OS tuning, full compute sizing, runner capacity |
| `05_Deployment_and_Operations_Spec.md` | Environments, containers, secrets, CI/CD, releases, monitoring, backups, runbooks, event timeline |
| `06_Security_Compliance_and_Gaps_Spec.md` | Threat model, authorization matrix, privacy, anti-cheat, runner hardening, accessibility, and the "things you may not be considering" checklist |

## 2. Conventions

- **MUST / SHOULD / MAY** are normative, as in the architecture.
- **Default** = a configurable starting value, not a decision. Defaults live in event configuration and are frozen at publication.
- **[OPEN]** = an undecided item. All open items are collected in §7.
- **Estimate** = a planning number to be replaced by measurement (architecture principle 8).
- **IDs:** `P-nn` participant page, `A-nn` admin page, `C-nn` component, `API-nn` endpoint group, `T-` database table, `JOB-` background job, `RB-` runbook, `NET-` network item, `SEC-` security control, `GAP-` unconsidered item.

## 3. Platform layer vs event layer

The platform is **event-agnostic**. This event is one configuration of it.

| Platform term | This event |
|---------------|-----------|
| Event | Bug Hunt CTF |
| **Stage** | A "Level" (1 to 4) |
| **Node** | Explanation page or execution page |
| Submission kind | `flags` (Levels 1-2), `upload` (Levels 3-4); other events may use `answer` (plain CTF flags) |
| Evaluator type | `match_flags` (1-2), `run_tests` (3), `run_tests_and_docs` (4) [OPEN: D-04] |
| AI assessment | Optional per stage |
| Runner | Optional per stage (off for simple CTFs) |
| Selection | A team-level one-time choice (here: the repo option) |

Code and tables use **stage**; the UI says **Level**.

## 4. Planning assumptions (change these and the numbers change)

| ID | Assumption | Used for |
|----|-----------|----------|
| AS-01 | 50 participants maximum in the first event | All capacity maths |
| AS-02 | About 10 to 12 teams of 4 to 5 | Team-level load, leaderboard size |
| AS-03 | 4 stages; execution windows of 45 to 90 minutes; total event 4 to 6 hours [OPEN: D-12] | Write volume, soak test |
| AS-04 | Each repo ≤ 20 MB and ≤ 2,000 files | Bundle and file API sizing |
| AS-05 | Average 10 and maximum 30 flags per participant per Level 1-2 | Submission and AI load |
| AS-06 | One AI assessment call per flag, about 2,000 input and 300 output tokens | AI queue and spend |
| AS-07 | A build/test run takes 15 to 60 s of one CPU core (stack dependent) | Runner sizing |
| AS-08 | Participants run builds about once per 3 to 5 minutes while active in Levels 3-4 | Runner sizing |
| AS-09 | All participants may sit behind one venue public IP | Rate limits |
| AS-10 | Free-tier allowance is 2 OCPU and 12 GB RAM in total (as the architecture records for Oracle A1) | Compute plan |

## 5. Global invariants (carry across every document)

1. The server decides time, eligibility, progression, verdicts and scores. The client only displays.
2. PostgreSQL is the only source of truth. Everything else is disposable.
3. The answer key, hidden test inputs and expected outputs exist only in the `gt` schema. No participant-facing process can read them.
4. Participant code executes only on the isolated runner. Never on the API, database, evaluator or admin hosts.
5. Every state-changing request is authorized, validated, audited and (for mutations that clients retry) idempotent.
6. Acknowledged means committed. A locally queued item is never shown as accepted.
7. The ledger and audit log are append-only. Corrections append reversal or adjustment entries.
8. AI never accepts, rejects or penalizes. It gives a capped partial score computed from rubric criteria. Stored results are reused on rescoring.
9. Every non-essential feature has a kill switch with a documented failure behavior.
10. Capacity claims are measured. The event cap equals the largest fully tested participant count.
11. A level, once submitted, cannot be re-entered by that participant.
12. Each repo choice is made once per team and never changed.

## 6. Glossary

| Term | Meaning |
|------|---------|
| Award unit | One independently scoreable bug or root cause (`award_unit_id`) |
| Flag | One bug report in Levels 1-2 |
| Runnable | Code attached to a submission for an official run |
| Practice run | A participant's own Run/Build; never scored |
| Official run | Evaluator-created run with hidden inputs; produces the output score |
| Gate | Server check that decides whether a node may be entered |
| Node pointer | A participant's current position, held by the server |
| Kill switch | Admin-controlled feature flag that disables a subsystem safely |
| Step-up | Fresh re-authentication within five minutes for sensitive actions |
| Ledger | Immutable list of score entries |
| Outbox | Table of side-effect intents delivered at least once |
| Seal | Final preparation of a challenge package (bundles, indexes, watermarks) |

## 7. Decisions still open (consolidated)

Items D-01 to D-12 come from the participant website spec. New ones from this set:

| ID | Question | Recommendation |
|----|----------|----------------|
| D-13 | Runner capacity plan: stay on the free tier (about 1 to 2 builds per minute in total) or add paid, temporary compute for Levels 3-4? | Add temporary runner compute for Levels 3-4 only; see `04` §7 |
| D-14 | Team size, number of teams, and whether teams can change after registration | Fix teams at registration; allow admin-only changes |
| D-15 | Exact durations and start times of all stages and nodes | Define in event config before sealing |
| D-16 | Repo size and file-count limits per repo option | 20 MB and 2,000 files (AS-04) |
| D-17 | Email provider for invites, resets and announcements | Any provider with SPF/DKIM/DMARC; free tier is enough |
| D-18 | Human support channel during the event (chat, phone, venue desk) | One named channel, monitored by the communications lead |
| D-19 | Single active session per participant? | Yes, with a clear "signed in elsewhere" message |
| D-20 | Data retention periods (see `03` §9) | Defaults in `03`; confirm with the privacy owner |
| D-21 | Results timeline: when are scores final and published? | Tied to measured review and evaluation capacity |
| D-22 | AI provider, model and what data is sent | Third-party API, minimal excerpt, named in the privacy notice |
| D-23 | Certificates, prizes and winner verification process | Define before the event; verification needs identity checks |
| D-24 | Post-event: keep a practice mode online or tear everything down | Archive, export, then tear down; keep read-only results |

## 8. Document status and change control

| Item | Rule |
|------|------|
| Versioning | Each file carries a version; changes go through pull request with at least one reviewer from another workstream |
| Conflicts | Record as a *Conflict* note and update the architecture via ADR |
| Estimates | Replace with measured numbers after the first load test, and update `04` |
| Review | Re-read all seven files together before the launch gate |
