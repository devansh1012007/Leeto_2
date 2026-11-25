# OPEN_DECISIONS.md

Each decision is a human decision. Defaults are taken from `docs/PLAN.md` §1 and are
**locked as defaults** until a human changes them. A0 blocks Phase 5 on DEC-13/DEC-14.

| ID | Question | Decision | Status | Locked at |
|----|----------|----------|--------|-----------|
| D-25 | Target participant count N and hosting profile | **N=50**; single VM (D1) + separate runner VM | locked (default) | Phase 0 |
| D-02 | Team-level vs participant-level award dedupe | **Team-level dedupe** (per `07` review R-04 recommendation): one effective award per `(team, stage, award_unit)` | locked (default) | Phase 0 |
| D-19 | Single active session per participant? | **Yes, with supersession** (new login supersedes; old session gets `AUTH_SESSION_SUPERSEDED`) | locked (default) | Phase 0 |
| D-04/D-05 | Level 3/4 scoring model | Level 3 hidden tests + Level 4 test-catch credit + AI on docs (per `02` §9.3 proposal) | locked (default) | Phase 0 |
| DEC-11 | AI `ai_share` per stage | **0.4** for stages with `ai_share > 0` | locked (default) | Phase 0 |
| DEC-13 | AI provider | **local** (Ollama-compatible adapter; stub in dev). `remote` requires privacy-notice bump | locked (default) | Phase 0 |
| DEC-14 | Runner hosting | **Separate VM in prod** (compose profile `runner-vm`); same-host container only dev/staging with no real data | locked (default) | Phase 0 |
| R-02 / D.2 | Same-host runner allowed in prod? | **No.** If a separate VM is unavailable, runner stays off (deterministic-only scoring) | locked (default) | Phase 0 |
