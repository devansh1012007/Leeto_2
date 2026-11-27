# 01 Frontend Specification

**Covers:** stack, global behavior, design tokens, component catalog, every participant page, every admin page, frontend testing.
**Related:** `Bug_Hunt_CTF_Participant_Website_Spec.md` (event flow), `02_Backend_Spec.md` (APIs), architecture §5.

---

## 1. Stack, structure and budgets

### 1.1 Stack
| Concern | Choice | Reason |
|---------|--------|--------|
| Language | TypeScript, `strict: true`, no implicit any | Catch contract drift at compile time |
| UI | React 18 | Common, large ecosystem |
| Build | Vite, ES modules, content-hashed filenames | Fast builds, cache-friendly |
| Routing | React Router (data router) | Guards, loaders, `replace` navigation |
| Server state | TanStack Query | Caching, retry, polling |
| Client state | Zustand (UI), component state (forms) | Small and simple |
| Forms | react-hook-form + zod | Validation shared with runtime schemas |
| Styling | Tailwind CSS + CSS variables for tokens | Consistent tokens, dark mode ready |
| Editor | Monaco, self-hosted, lazy-loaded, only needed language workers | CSP-friendly, no CDN dependency |
| Local storage | `idb` (IndexedDB wrapper) | Drafts and outbox |
| API client | Generated from OpenAPI in CI | No drift |
| Tests | Vitest, Testing Library, Playwright, axe-core, MSW | Unit, e2e, accessibility |
| Lint/format | ESLint (strict), Prettier, `tsc --noEmit` in CI | Quality gate |

Pin exact versions in the lockfile. Update dependencies by pull request only, never during the change freeze.

### 1.2 Repository layout
```
frontend/
  apps/
    participant/   src/{routes,features,layouts,main.tsx}
    admin/         src/{routes,features,layouts,main.tsx}
  packages/
    api-client/    generated types + fetch wrapper
    ui/            design system components (C-xx)
    workspace/     editor shell, explorer, flag panel, build panel
    clock/         server offset + countdown
    storage/       IndexedDB layer, outbox, draft sync
    validation/    zod schemas
    copy/          message catalog (English), warning texts, placeholder pool
    config/        tsconfig, eslint, tailwind presets
```
Rules: the participant app MUST NOT import from `apps/admin` or contain admin routes. A CI check greps the participant build output for admin route names, ground-truth words and secret patterns.

### 1.3 Performance budgets (participant app)
| Item | Budget |
|------|--------|
| Initial JS (landing, gzip) | ≤ 180 KB |
| Dashboard route chunk | ≤ +80 KB |
| Workspace chunk (Monaco + needed workers, gzip) | ≤ 3 MB, prefetched on explanation pages |
| LCP (landing, mid laptop, broadband) | ≤ 2.5 s |
| INP | ≤ 200 ms |
| CLS | ≤ 0.1 |
| Editor open (file switch, cached) | ≤ 150 ms |
| Memory (workspace tab, 1 hour) | no unbounded growth; ≤ 600 MB resident |

### 1.4 Browser and device support
Current stable Chrome, Edge, Firefox (and Safari, best effort for non-execution pages). Execution pages need width ≥ 1024 px and a pointer or keyboard; otherwise show P-24 (unsupported device). Informational pages are responsive from 360 px.

### 1.5 Build and config
- Runtime config is fetched from `/config.json` (not baked in): API base URL, min client version, feature flag defaults. No secrets, ever.
- Source maps are uploaded to the error tracker, not served publicly.
- `index.html` is revalidated; assets are `immutable` with one-year caching.
- CSP forbids inline scripts. Monaco workers are loaded from same origin with an explicit `worker-src`.

---

## 2. Global behavior

### 2.1 App boot sequence
1. Load shell. Read `/config.json`.
2. `GET /v1/time` (3 samples) → compute clock offset (lowest-latency sample).
3. Try silent refresh (`POST /v1/auth/refresh`, credentials included) → access token into memory.
4. If signed in: `GET /v1/me`, then `GET /v1/state`. Else public pages only.
5. Check `X-Min-Client-Version`. If the client is too old, show a blocking "Reload to update" screen.
6. Route to the requested page or the node pointer's page (guard, §2.3).

### 2.2 Session handling
- Access token in memory only. Refresh through Web Locks across tabs (BroadcastChannel fallback).
- Expired refresh → save drafts locally, show P-23 "Session expired", sign in again, return to the same node.
- If the server reports another active session (D-19), show P-23 variant "Signed in on another device". Drafts remain stored and are offered for restore.

### 2.3 Route guards
`beforeLoad` for protected routes: (a) ensure signed in; (b) fetch `GET /v1/state`; (c) compare the requested node with the node pointer and level statuses; (d) redirect forward with a toast if blocked. Guards are convenience. The server re-checks on every data request.

### 2.4 Polling manager (single source of live data)
| Item | Rule |
|------|------|
| Endpoint | `GET /v1/state` (aggregate: server time, node pointer, node states and deadlines, team score and version, leaderboard version, announcements, kill-switch flags, min client version, gate hints) |
| In a round | Every 5 s with ±20% jitter |
| Outside a round | Every 30 s |
| Tab hidden | Every 30 s; immediate refresh on visibility |
| Triggers | Window focus, `online` event, after any mutation, route change |
| Errors | Exponential backoff 5 → 10 → 20 → 30 s; connection indicator shows *Reconnecting* |
| Leaderboard | Fetched only when `leaderboard_version` changed (`GET /v1/leaderboard?since=`) |
| Cache | Last good state kept in memory and IndexedDB for instant paint |

### 2.5 Local storage layer (IndexedDB `bhctf-v1`)
| Store | Key | Value |
|-------|-----|-------|
| `workspace` | `[userId, stageId]` | open tabs, pane layout, active file, cursor, scroll, panel state, `updatedAt`, `serverVersion` |
| `files` | `[userId, stageId, path]` | content, `baseHash`, `dirty`, `localVersion` |
| `flags` | `[userId, stageId]` | flag list, `updatedAt`, `serverVersion` |
| `outbox` | `requestId` | method, URL, body, idempotency key, attempts, status |
| `cache` | name | payload, ETag, `fetchedAt` (leaderboard, content) |
| `ui` | key | preferences (theme, sidebar width, reduced motion override) |

All stores are wiped on explicit sign-out. A stage's `workspace`, `files` and `flags` entries are deleted only after the server acknowledges the stage submission (`202`). If IndexedDB is unavailable (private mode), run in memory with a persistent warning: "Your work is only saved to the server."

### 2.6 Draft sync protocol
- Triggers: 10 s after the last change, file switch, panel close, `visibilitychange`, `pagehide` (via `sendBeacon`), navigating to the Dashboard.
- Only **changed files** are sent, each with `base_version`. Unchanged files are never re-sent. Limit: 512 KB per request (default).
- Server response includes the new `version` and `server_saved_at`. A version conflict (`409 DRAFT_VERSION_CONFLICT`) opens a merge prompt: *Keep mine*, *Use server*, *Compare*.
- Status chip states: `Saved locally`, `Saved to server`, `Offline: changes kept on this device`, `Submit queued, not accepted yet`, `Submission accepted`.

### 2.7 Outbox
Mutations that must survive a flaky network (draft sync, submit, repo lock) carry a stable `Idempotency-Key`. They are stored in `outbox`, retried with backoff while online, and shown to the user as *queued*. A queued submit is never displayed as accepted.

### 2.8 Warning and notification system
| Class | Behavior | Examples |
|-------|----------|----------|
| Toast | Auto-dismiss 6 s, polite live region | "Draft saved", "Flag added" |
| Banner | Persistent at the top until dismissed or resolved | 2-minute start warning, offline |
| Blocking alert | Modal, focus trapped, requires action | Repo not locked, "Time's up" |
| Inline | Next to a field | Flag validation |
| Escalation | Same message repeated at fixed thresholds | 5, 3, 1 minute to deadline |

Messages come from `packages/copy` with keys (for example `warn.deadline.5m`) so wording can be changed without code changes.

### 2.9 Connection indicator
Always visible in the workspace header. States: *Online*, *Reconnecting*, *Offline (work kept locally)*, *Server degraded* (from `state.flags`), *Runner unavailable*. Colour plus icon plus text.

### 2.10 Maintenance mode and kill switches
`state.flags` can hide or disable: leaderboard, Run/Build, AI-derived displays, announcements, uploads. A disabled feature shows an explanation, never an empty hole. `maintenance=true` shows P-24 maintenance page with the status link; sign-in remains available to admins.

### 2.11 Keyboard shortcuts (workspace)
| Keys | Action |
|------|--------|
| `Ctrl/Cmd+P` | Quick open file |
| `Ctrl/Cmd+\` | Split editor |
| `Ctrl/Cmd+B` | Toggle sidebar |
| `Ctrl/Cmd+Shift+F` | Toggle flag panel (Levels 1-2) |
| `Ctrl/Cmd+Enter` | Add current selection to the active flag |
| `Ctrl/Cmd+Shift+Enter` | Run/Build (Levels 3-4) |
| `Esc` | Close modal, panel or progress bar pin |
| `?` | Shortcut help |

Shortcuts MUST NOT override native browser text-editing keys. Shortcuts are listed in a help dialog.

### 2.12 Error handling
- Error boundary per route and per major panel. A panel failure never takes down the whole app.
- Standard error envelope handled centrally: show `message`, include `request_id` with a "Copy details" button for support.
- Unknown errors: "Something went wrong. Your work is saved." (only if it truly is, based on sync state).

### 2.13 Internationalisation and time
English only in the first event. All strings use catalog keys so another language can be added. Dates and times display in the **event's time zone** (default `Asia/Kolkata`) with the zone abbreviation shown on schedules; countdowns are time-zone independent.

---

## 3. Design tokens

### 3.1 Colour roles (semantic, not literal)
`bg`, `surface`, `surface-raised`, `border`, `text`, `text-muted`, `accent`, `accent-contrast`, `success`, `warning`, `danger`, `info`, `focus-ring`, `overlay`, `editor-bg`. Each has light and dark values. Contrast: normal text ≥ 4.5:1, large text and UI parts ≥ 3:1. Warnings use icon plus text, never colour alone. Dark mode is the default inside the workspace; the rest follows the OS setting. A user override is stored in the `ui` store.

### 3.2 Type, spacing, shape
| Token | Values |
|-------|--------|
| Fonts | UI: system sans stack; code: a monospace stack with ligatures off |
| Type scale | 12, 14 (body), 16, 18, 20, 24, 30, 36 px |
| Line height | 1.5 body, 1.3 headings |
| Spacing | 4 px base: 4, 8, 12, 16, 24, 32, 48, 64 |
| Radius | 4, 8, 12 px |
| Z-index layers | content 0, sticky 10, progress bar 20, panels 30, dropdown 40, modal 50, toast 60 |

### 3.3 Motion
| Token | Value |
|-------|-------|
| Fast / base / slow | 120 / 200 / 300 ms |
| Easing | ease-out for enter, ease-in for exit |
| Progress bar expand | 150 ms |
| Flag panel reveal | 280 ms |
| Reduced motion | all transitions become 0 ms fades or instant; no parallax or large movement |

---

## 4. Component catalog

Every component lives in `packages/ui` or `packages/workspace`, has Storybook-style examples (or equivalent), a11y tests and documented states.

### 4.1 Foundation
| ID | Component | Key props | States | A11y / notes |
|----|-----------|-----------|--------|--------------|
| C-01 | Button | variant, size, loading, disabled, `aria-busy` | default, hover, focus, active, loading, disabled | Min target 40 px; loading keeps width |
| C-02 | IconButton | label (required) | same | Needs `aria-label` |
| C-03 | TextInput, Textarea | label, error, hint, counter | default, error, disabled | Label always visible; counter live region at limit |
| C-04 | Checkbox, Radio | label, description | checked, disabled, error | Real inputs, large hit area |
| C-05 | Select / Combobox | options, async | open, empty, loading | File suggestions in flag form |
| C-06 | Tabs | items | selected, overflow | Arrow-key navigation |
| C-07 | Modal | title, dismissible, initialFocus | open, closing | Focus trap, returns focus, `Esc` closes unless blocking |
| C-08 | ConfirmModal | title, body, confirmLabel, cooldownSeconds, safeDefault | cooldown, ready | Cooldown announced each second at most every 5 s; safe button default focus |
| C-09 | Toast / ToastRegion | type, message, duration | enter, exit | Polite live region |
| C-10 | Banner | severity, action, dismissible | visible, dismissed | `role=status` or `alert` by severity |
| C-11 | Tooltip, Popover | content, trigger | open | Keyboard and touch triggers, not hover-only |
| C-12 | Skeleton, Spinner, EmptyState, ErrorState | variant | n/a | Skeletons match final layout to avoid CLS |
| C-13 | Badge, StatusChip | tone, label | n/a | Text plus icon |
| C-14 | Card, Panel, SplitPane | resizable | dragging | SplitPane keyboard-resizable |
| C-15 | Table / List (virtualised) | columns, rows | loading, empty | Used by leaderboard and admin |
| C-16 | Markdown / RichContent | source (sanitised) | n/a | Strict sanitiser; images with alt text |

### 4.2 Event components
| ID | Component | Purpose | Key props / data | States and rules |
|----|-----------|---------|------------------|------------------|
| C-20 | ProgressBar | Event-wide progress and countdown | `GET /v1/state` | collapsed / expanded / pinned; see Participant Website Spec §3.1; `nav` landmark; percentage text for screen readers |
| C-21 | Countdown | Server-synced time remaining | `deadline`, `format`, `onZero` | Never decides lateness; on zero it refetches state |
| C-22 | LevelCard | One level on the Dashboard | status, title, window | upcoming, available, in progress, submitted, auto-submitted, missed |
| C-23 | TeamPanel | Members, lead badge, per-member status, repo choice | team data | Updates from state; lead badge has text |
| C-24 | ScoreCard | Team score | score, version | Animates on change; live region announces |
| C-25 | Leaderboard | Ranked teams | snapshot, my team | Pins own row; frozen/hidden banners; reorder animation (reduced-motion safe) |
| C-26 | GateButton | Start button with backend check | levelId | disabled(waiting + reason), enabled, checking, closed; polls every 5 s while waiting |
| C-27 | AnnouncementBar | Organizer announcements | list | Dismissible per announcement id; critical ones persist |
| C-28 | ConnectionIndicator | Connectivity and degradation | state | See §2.9 |
| C-29 | StatusChip (sync) | Draft and submit sync state | state enum | See §2.6 |
| C-30 | RepoOptionCard | One of two project options | option data | selected, disabled (non-lead), locked |
| C-31 | RepoLockSection | Caution box, radios, checkbox, lock button, modal | team, lead flag | See Participant Website Spec §4.5; server errors shown inline |
| C-32 | ExplainContent | Level explanation with screenshots | content blocks | Images have alt text, lazy-loaded, fixed aspect ratio |

### 4.3 Workspace components
| ID | Component | Purpose | Notes |
|----|-----------|---------|-------|
| C-40 | WorkspaceShell | Header, sidebar, panes, bottom panel | Resizable regions; layout persisted per stage |
| C-41 | FileExplorer | Repo tree | Virtualised; keyboard tree pattern; search (Levels 3-4); shows only the team's repo; badges for modified files (editable stages) |
| C-42 | EditorPane | One Monaco instance with tabs | Read-only (Levels 1-2) or editable (3-4); tab cap 8; dispose models on close; line numbers; selection event emitter |
| C-43 | EditorSplit | Two panes side by side | Same file may open in both; independent scroll |
| C-44 | QuickOpen | Fuzzy file search | `Ctrl/Cmd+P` |
| C-45 | FlagPanel | Bottom panel hosting flags | Reveal animation; see Website Spec §3.5 |
| C-46 | FlagForm | One flag | Fields: file, lines, explanation; Level 2: locations list |
| C-47 | LocationRow | One `(file, lines)` entry | Validation against repo tree and file length |
| C-48 | FlagList | Tabs or list of flags with add/delete | Per-flag validity badge; max flags message |
| C-49 | PlaceholderPicker | Chooses random funny placeholder | Picked once per flag, persisted with the flag draft, never submitted |
| C-50 | BuildPanel | Run/Build controls and output | States: idle, queued, running, finished, timed out, killed, unavailable; plain text only |
| C-51 | OutputViewer | stdout/stderr tabs, exit status, truncation notice | Never interprets HTML |
| C-52 | UploadDropzone | Zip/diff upload | Drag-drop plus file picker; shows name, size, checks, progress; cancel; error details |
| C-53 | DiffExportButton | Generates `.diff` from saved workspace | Shows size and file count first |
| C-54 | SubmitDialog | Final submission confirmation | Summary of flags or files; warning "can't go back"; idempotent submit |
| C-55 | DraftSync | Invisible controller | Implements §2.6 |

### 4.4 Admin components
| ID | Component | Purpose |
|----|-----------|---------|
| C-60 | DataTable (server-paginated, cursor) | Participants, submissions, audit |
| C-61 | FilterBar | Saved filters, URL-synced |
| C-62 | StepUpDialog | Re-authenticate for sensitive actions |
| C-63 | ReasonDialog | Requires a written reason before pausing, rescoring, overriding |
| C-64 | DiffViewer | Compare config revisions, challenge versions |
| C-65 | ChecklistEditor | Readiness checklist with owner and state |
| C-66 | ReviewWorkbench | Report, candidate bug, code view, AI panel, decision form |
| C-67 | KillSwitchPanel | Toggles with confirmation, state, last change, who |
| C-68 | ScheduleEditor | Timeline editor for stage times with validation |
| C-69 | JsonConfigEditor | Typed form plus read-only JSON preview with schema validation |
| C-70 | AuditEntryView | Entry, actor, before/after (redacted), chain verification state |

---

## 5. Participant pages

Conventions for every page: *Access* names the guard; every page has loading, error and offline states; every page includes the progress bar once signed in (except sign-in and public pages); focus moves to the page heading on route change; the document title is set.

### P-01 Landing (`/`)
- **Access:** public. **Purpose:** welcome and lead to sign-in.
- **Layout:** hero (event name, countdown, sign-in button) → event brief → rules brief → links (Event details, Level 1 preview if public [OPEN: D-08]) → footer (privacy, terms, support, status).
- **Data:** `GET /v1/event/public` (cacheable).
- **States:** before start (countdown), live ("The event is live"), ended ("The event has ended"), maintenance.
- **Actions:** Sign in. If a session exists, the button is "Go to dashboard".
- **Edge cases:** the countdown uses server time; a wrong laptop clock changes nothing. At zero it refetches rather than flipping locally.
- **A11y:** the countdown is not announced each second; announce at 10 min, 1 min, and zero.

### P-02 Sign-in (`/login`)
- **Fields:** identifier (email or username), password. Optional bot challenge on repeated failures.
- **States:** idle, submitting, wrong credentials (generic), rate-limited (with retry time), account not found (generic), account locked, system unavailable.
- **After success:** if rules/consent version not accepted → P-03; else to the requested page or Dashboard.
- **Links:** "Forgot password" (P-04), support.
- **Security:** no user enumeration; password field `autocomplete=current-password`; no tokens in URLs.

### P-03 Rules and consent gate (`/consent`)
- Shows current rules version, privacy notice summary, telemetry notice, AI-processing notice. Requires explicit checkboxes. Stores acceptance with version and time. Blocks all pages until accepted. Re-appears when the rules version changes.
- Actions: Accept and continue; Download rules (PDF); Sign out.

### P-04 Account activation and password reset (`/activate`, `/reset`)
- Invite token in the URL (single-use, short-lived, removed from the URL after load). Set password with strength meter and clear rules. Reset by email. Expired and used token states with a request-new-link option.

### P-05 Dashboard (`/dashboard`)
- **Access:** signed in. **Layout:** header (team name, participant name, team info corner) → progress bar → grid: ScoreCard, Leaderboard, LevelCards, TeamPanel, Resume button, Event details link, AnnouncementBar.
- **Data:** `GET /v1/state`, `GET /v1/team`, `GET /v1/leaderboard`.
- **Resume button label:** dynamic from node pointer. States: *Event not started*, *Resume: Level N explanation*, *Resume: Level N execution*, *All done*.
- **Behavior:** arriving from a workspace triggers a draft flush first; the Resume button restores the workspace.
- **Edge cases:** leaderboard hidden or frozen banners; participant without a team (error page with support link).

### P-06 Event details (`/event`)
Public content page with a table of contents: Overview, How it works, How to take part, Scoring, How to win, Road map, Rules summary, FAQ, Support. Anchors are linkable. Content from `GET /v1/content/event-details`. Road map shows stage times in the event time zone.

### P-07 Level 1 explanation and repo lock (`/level/1/explain`)
- Spec in Website Spec §4.5. Additional technical points:
  - The lock section is rendered from `GET /v1/team` (`is_lead`, `repo_choice`).
  - `POST /v1/team/repo-lock` is sent with an idempotency key. `409 ALREADY_LOCKED` shows the existing choice instead of an error.
  - The 7-second cooldown is UI only; the server independently enforces lead-only and one lock.
  - Blocking alert on countdown end for the lead if not locked; scroll to the lock section and focus the radio group.
  - Prefetch the workspace chunk and the repo tree for the chosen option after locking.

### P-08 Know-more pages (`/level/1/repo/a`, `/level/1/repo/b`)
README rendered from `GET /v1/repo-options/{key}/readme` (sanitised Markdown). Includes project description, stack, run instructions (for reading only), and screenshots. A Back button restores the previous scroll and selection. Marked "informational; no work happens here".

### P-09 Explanation pages for Levels 2 to 4 (`/level/:n/explain`)
One generic page driven by content for `(level, repo option)`. Blocks: explanation, target, screenshots, worked-example link, countdown, GateButton, rules link.
- Banner at last minute of the window: "Time is almost up. Go to the execution page."
- If the previous level isn't complete for all teammates: GateButton shows who is waiting.

### P-10 Execution pages, Levels 1 and 2 (`/level/:n/run`)
- **Config:** read-only editor, flag panel, no Run panel. Level 2 enables multi-location flags.
- **Layout:** header (Rules, Explain, Dashboard, timer, status chip, connection indicator, Flag button) → progress bar → sidebar | EditorSplit → bottom FlagPanel.
- **Data:** `GET /v1/repo/tree`, `GET /v1/repo/files/{path}` (ETag), `PUT /v1/drafts/{stage}`, `POST /v1/stages/{n}/submit`.
- **Flag form validation:**

  | Field | Rule | Error text key |
  |-------|------|----------------|
  | File | must exist in the tree | `flag.file.unknown` |
  | Lines | `N` or `N-M`, 1 ≤ N ≤ M ≤ file length, max span 200 lines (default) | `flag.lines.invalid` |
  | Explanation | 10 to 1000 characters, plain text | `flag.explanation.length` |
  | Flag count | ≤ stage cap (default 30) | `flag.cap.reached` |

- **Submit flow:** SubmitDialog → idempotent `POST` → on `202` delete local data and `replace` to next explanation page. On failure the draft stays and the outbox retries.
- **Auto-submit:** warnings at 5, 3, 1 minute; at 0 flush draft, show "Time's up. Auto-submitting…", poll state until the server confirms, then redirect.
- **Edge cases:** server-time drift; participant opens the page after the deadline (redirect to the next node with a message); two tabs (second tab shows read-only "Open in another tab" notice).

### P-11 Execution pages, Levels 3 and 4 (`/level/:n/run`)
- **Config:** editable Monaco, BuildPanel, UploadDropzone, DiffExportButton, no flag panel.
- **Layout:** header → progress bar → sidebar | EditorSplit → bottom BuildPanel (collapsible) → Submit button in header.
- **Editing:** edits are kept as per-file deltas against the base hash. Revert-file action. A "modified files" list in the sidebar.
- **Build/Run:** `POST /v1/runs`; poll `GET /v1/runs/{id}` every 1 s while running (backoff to 3 s); Stop = cancel. Output is plain text, capped. Runs-left counter and limits visible.
- **Submit:** opens SubmitDialog with two paths:
  1. **Upload** `.zip` / `.diff` / `.patch` via UploadDropzone (client checks type and size; server re-checks).
  2. **Export first**: DiffExportButton generates the file from the saved workspace so the participant can upload it.
- **Pre-submit check:** server dry-run `POST /v1/uploads/{id}/validate` reports patch-apply problems before the participant confirms.
- **After submit:** `replace` to the next explanation page (Level 3 → 4) or the Dashboard (Level 4).
- **Edge cases:** huge files (Monaco read-only fallback above 2 MB); binary files (shown as "binary, not editable"); runner unavailable (BuildPanel shows reason, editing and submitting still work).

### P-12 Rules page (`/level/:n/rules`)
Level rules plus event rules, searchable, with a table of contents. Opens as a side panel from the workspace (state preserved) or as a page elsewhere. Content versioned; shows version and last updated time.

### P-13 Explain / guide page (`/level/:n/guide`)
What to do in this level, plus one worked example in the team's chosen repo. Code blocks are static, not part of the editor. Includes "common mistakes" and "what we score" sections.

### P-14 Submission receipt and evaluating (`/level/:n/receipt`)
Shown briefly after submit, or from the Dashboard. Shows the receipt code, time accepted (server time), counts (flags or files), and the status (*received*, *evaluating*, *evaluated*). No per-flag verdict while the stage feedback mode is `hidden`.

### P-15 Finished and results (`/results`)
Before finalization: "Your team has finished. Results are pending." After finalization: team score by level and component, rank, tie-break note, per-flag outcomes **only** if the event publishes them, link to dispute (P-16).

### P-16 Dispute (`/results/dispute`)
Form: which item, reason (plain text, limit), optional evidence. Deadline countdown. Status tracking. One open dispute per item. Submitting is idempotent.

### P-17 Team (`/team`)
Members, roles, per-level status, repo choice. Read-only for participants. Lead sees nothing extra here (the lock lives on P-07).

### P-18 Profile and sessions (`/profile`)
Name, email (read-only), change password, active sessions list with sign-out-others, consent versions accepted, data request link.

### P-19 System check and lobby (`/lobby`)
Pre-event readiness: browser version, IndexedDB available, storage quota, WebCrypto, Web Locks, clock offset and drift, network latency to API, bundle prefetch progress, Monaco loaded, runner availability (warn only). Each check pass/warn/fail with fix hints. Includes a short tour (skippable). Available from the Dashboard before the event and during it.

### P-20 Practice mode (optional platform feature)
Same workspace on a separate practice repo and answer key (`practice` schema). Instant feedback allowed. Hidden when practice is off.

### P-21 Announcements (`/announcements`)
Chronological list of organizer messages with timestamps and severity. New items also appear in the AnnouncementBar.

### P-22 Support (`/support`)
Support channel link, FAQ search, "Report a problem" form that attaches `request_id`, client version, browser, last sync state. Never collects code or answers.

### P-23 Session states
*Session expired*, *Signed in elsewhere*, *Account disabled*, *Disqualified (with appeal link)*. Each has one clear next action.

### P-24 System pages
*Not started*, *Ended*, *Maintenance*, *Unsupported device or browser*, *403 Forbidden*, *404 Not found*, *500 error*, *Offline*. All include the status page link and request ID when available.

---

## 6. Admin pages

All admin pages require Cloudflare Access identity, an application admin session with MFA, and the stated permission. Sensitive actions require step-up and a reason.

| ID | Page | Route | Permission | Purpose and key content |
|----|------|-------|-----------|--------------------------|
| A-01 | Sign-in and step-up | `/login` | n/a | Access identity check, then MFA (TOTP or WebAuthn) |
| A-02 | Admin home | `/` | any admin | Health summary, next scheduled transition, queue ages, pending reviews, readiness progress, recent audit |
| A-03 | Events list | `/events` | organizer | Events with status, dates, participant counts |
| A-04 | Event detail and config | `/events/:id` | organizer | Revisioned config (time zone, branding, rules version, feedback modes, ai/runner flags); diff between revisions; publish freezes it |
| A-05 | Stage configuration | `/events/:id/stages` | organizer | Per stage: kind, node list, evaluator type, AI on/off, runner on/off, caps (flags, runs, upload size), `ai_share`, scoring weights, feedback mode |
| A-06 | Schedule and timers | `/events/:id/schedule` | organizer | Timeline of `explain_opens_at`, `exec_opens_at`, `exec_closes_at`; validation (no overlaps, buffers); preview as participant |
| A-07 | Participants and import | `/events/:id/participants` | organizer | CSV import with dry-run validation, duplicate detection, per-row errors; search; disable/enable; resend invite |
| A-08 | Teams | `/events/:id/teams` | organizer | Create/edit teams, assign lead and members, lock after publish, change log |
| A-09 | Repo options | `/events/:id/repo-options` | organizer | Define options (key, title, stack, description), link challenge packages, set README content, difficulty parity notes |
| A-10 | Challenge packages | `/challenges` | author | List with status (DRAFT to ARCHIVED), versions, hashes |
| A-11 | Challenge upload and validation | `/challenges/new` | author | Safe archive upload, validation report (paths, sizes, languages, hashes, line counts, anchors), errors with fixes |
| A-12 | Challenge detail | `/challenges/:id` | author | Files, tree, hashes, review state, unplanned-defect audit notes, freeze, seal, publish; sealing progress |
| A-13 | Ground-truth editor | `/challenges/:id/ground-truth` | ground-truth role + step-up | Bugs, award units, locations and line anchors, aliases, severity, category; revision history; banner "ground truth visible" |
| A-14 | Test cases editor | `/challenges/:id/tests` | ground-truth role + step-up | Hidden inputs, expected outputs, comparison mode, weights; dry-run against sample solution |
| A-15 | Rubric editor | `/challenges/:id/rubric` | ground-truth role + step-up | AI criteria with weights summing to 1, reference root-cause statement; hash shown |
| A-16 | Matcher harness | `/challenges/:id/harness` | ground-truth role | Paste sample report and runnable; see matcher result, AI result (dry-run), output result; writes nothing |
| A-17 | Content editor | `/content` | content editor | Event details, rules, explanation, guide pages per `(stage, repo option)`; versions; preview; screenshot library with alt text; warning-copy catalog; placeholder pool editor |
| A-18 | Live operations console | `/events/:id/live` | operator | Round state, pause/resume/extend (reason required), per-participant lookup, queue depth, announcements, kill switches, force-open or close a stage |
| A-19 | Kill switches | `/events/:id/switches` | operator | Toggles: leaderboard, runner, AI assessment, uploads, telemetry, practice, read-only mode, admission control; confirmation, reason, history |
| A-20 | Announcements | `/events/:id/announcements` | operator | Compose, schedule, severity, audience (all, team, participant), expire |
| A-21 | Review queue | `/review` | reviewer | Filter by stage, age, severity, assignee, status; capacity and backlog forecast |
| A-22 | Review workbench | `/review/:id` | reviewer | Report, candidate bugs with matcher features, ground-truth excerpt (permitted roles), AI assessment, official run result, decision form (accept full, partial, duplicate, invalid, unplanned bug), AI override with reason |
| A-23 | Disputes | `/disputes` | reviewer/organizer | Open disputes, evidence, second-reviewer assignment, decision |
| A-24 | Rescoring | `/events/:id/rescore` | organizer + step-up | Choose scope, ground-truth revision, rule set; dry-run diff of score changes; execute; reversal entries only |
| A-25 | Leaderboard control | `/events/:id/leaderboard` | organizer | Mode per stage (live, frozen, hidden), freeze now, publish snapshot, tie-break preview |
| A-26 | Finalization | `/events/:id/finalize` | organizer + step-up | Checklist: reviews done, disputes closed, ledger verified, snapshot taken, export; irreversible with confirmation |
| A-27 | Runner console | `/runner` | operator | Runner VM health, queue depth, running jobs, outcomes, kill a job, drain, enable/disable, image digests |
| A-28 | AI console | `/ai` | operator | Assessment queue, error rate, latency, spend vs budget, model/prompt/rubric versions, retry or route to review |
| A-29 | Integrity console | `/integrity` | integrity officer | Flags, cases, evidence, actions; disqualification needs two approvers |
| A-30 | Audit viewer | `/audit` | auditor | Search and filter, chain verification, checkpoint status, export |
| A-31 | Exports | `/exports` | organizer | Results, submissions, ledger, audit, participant data; formats and versions; access log |
| A-32 | System health | `/health` | operator | Service status, DB metrics, disk and WAL, archive lag, backup age, restore drill record, queue ages, error rates |
| A-33 | Readiness checklist | `/events/:id/readiness` | organizer | Launch gate items with owner, evidence link, state; the event cannot open until complete |
| A-34 | Users and roles | `/admin-users` | super-admin | Admin accounts, roles, MFA state, last login, disable; changes need step-up |
| A-35 | Settings | `/settings` | super-admin | Rules versions, consent versions, retention settings, email templates, domains |

### Admin UI rules
- Every destructive or sensitive action: confirm modal, **reason field**, and audit entry.
- Ground-truth, test-case and rubric pages show a persistent "sensitive data visible" banner and log views.
- Tables use cursor pagination and never load the whole dataset.
- All admin pages show the current event and environment (a red banner on production).
- Exports are generated server-side and delivered as expiring links.

---

## 7. Frontend testing and acceptance

| Layer | Content |
|-------|---------|
| Unit | Clock offset, polling manager backoff, draft diffing, validation schemas, countdown thresholds, flag validation, placeholder picker |
| Component | Each C-xx in all states, with axe checks |
| Integration (MSW) | Guard redirects, gate states, outbox retry, version-conflict merge, kill-switch UI |
| End-to-end (Playwright, real stack) | Full four-level journey with two users in one team; refresh and Dashboard round-trips; offline during submit; auto-submit; unauthorized URL access |
| Accessibility | Keyboard-only run of every page; screen-reader pass of the modals, flag form and progress bar; contrast and reduced-motion checks |
| Visual regression | Key pages at 1280, 1440, 1920 px and a narrow informational layout |
| Performance | Lighthouse budgets in CI for landing and dashboard; Monaco chunk size check |
| Bundle checks | No admin code or secrets in the participant build |
| Cross-browser | Chrome, Edge, Firefox on the e2e smoke path |

**Acceptance for the frontend** is the 16 scenarios in the Participant Website Spec §8, plus: the participant bundle contains no admin routes; every page has a title, heading and landmark; all warnings come from the copy catalog; every mutation shows the right sync-state text; and reduced-motion mode removes all non-essential animation.
