# Definition of Done

Single source referenced by every phase gate in `docs/GATES.md`.

## Per-agent DoD (template)

Every sub-agent task card is `pass` only when ALL of the following hold:

- Build green: `ruff check`, `mypy --strict` (module boundary), `tsc --noEmit` (frontend), `vite build` succeed.
- Tests green: the agent's own acceptance tests pass; no skipped tests without a linked `OPEN_QUESTIONS.md` entry.
- No warnings introduced (lint, type, build).
- No TODOs / FIXMEs / placeholder markers in new code.
- No secrets, tokens, keys, or ground-truth content in code, config defaults, logs, or client bundles.
- No `print()` statements; structured logging only.
- Error paths covered: every new endpoint returns only catalogued error codes.
- Frontend: `axe-core` 0 criticals on new pages, keyboard pass, loading/empty/error/offline states present.
- Backend: role test passed (the process's DB role can do what it must and nothing more).

## Per-phase DoD

- Every task card in the phase is `pass` with a file artifact.
- Every correction tagged to that phase in `docs/CORRECTIONS.md` is `applied` (or `accepted_deviation` with sign-off).
- Every gate item in `docs/GATES.md` for the phase has an evidence link (test log, command output, or rendered artifact).

## Global DoD (product launch)

- All 16 acceptance scenarios from `01 §7` pass against the real stack.
- All launch-gate items from `06 §10` have evidence artifacts.
- All items in `docs/CORRECTIONS.md` are `applied` or signed-off deviations.
- Every supported-N declaration is backed by a load-test record in `docs/CAPACITY.md`.
- Readiness checklist (A-33) signed by named owners.
