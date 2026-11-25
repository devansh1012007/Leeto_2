-- Bug Hunt CTF — complete schema DDL (A2, T-2.1..T-2.7)
-- Postgres 16. Every table carries tenant_id. Expand/contract only (see migration notes).
--
-- Corrections applied here:
--   R-03/E.1  answer packs live in gt; app_api has zero grants on gt.*
--   R-31      per-bug weight_multiplier default 1
--   R-32/E.1  AP entry overlapping a GT anchor rejected at INSERT (constraint trigger)
--   R-33/E.1  ledger: three origin columns + CHECK (num_nonnulls = 1)
--   R-16/B11  node pointer sub-states + adjusted_by/adjusted_reason
--   B4/R-15   idempotency: route column + partial unique + retention semantics
--   R-02      runner has NO database role at all

-- ============================================================ schemas
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS gt;
CREATE SCHEMA IF NOT EXISTS practice;
CREATE SCHEMA IF NOT EXISTS integrity;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS ops;

-- ============================================================ roles (03 §1)
-- passwords/secrets come from compose secrets at deploy time; never in this file.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_owner') THEN
    CREATE ROLE db_owner NOLOGIN;          -- migrations only
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_api') THEN
    CREATE ROLE app_api NOLOGIN;           -- participant API; NO grants on gt
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_api') THEN
    CREATE ROLE admin_api NOLOGIN;         -- admin API
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'worker') THEN
    CREATE ROLE worker NOLOGIN;            -- worker_general
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evaluator') THEN
    CREATE ROLE evaluator NOLOGIN;         -- worker_evaluator; the ONLY app-side gt reader
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'scheduler') THEN
    CREATE ROLE scheduler NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'runner_gw') THEN
    CREATE ROLE runner_gw NOLOGIN;         -- runs tables only, no gt
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auditor') THEN
    CREATE ROLE auditor NOLOGIN;           -- read-only exports
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gt_reader') THEN
    CREATE ROLE gt_reader NOLOGIN;         -- ground-truth admin UI reads
  END IF;
END $$;
-- NOTE (R-02): there is deliberately NO 'runner' role. The runner VM has no DB access.

-- ============================================================ app: tenancy & identity
CREATE TABLE IF NOT EXISTS app.tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES app.tenants(id),
  email citext NOT NULL,
  username citext NOT NULL,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('user','admin','reviewer','ground_truth','operator','auditor','super_admin')),
  mfa_secret text,
  disabled_at timestamptz,
  disqualified_at timestamptz,
  last_login_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email),
  UNIQUE (tenant_id, username)
);

CREATE TABLE IF NOT EXISTS app.sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app.users(id),
  refresh_token_hash bytea NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  superseded_by uuid,
  user_agent_hash text,
  ip_hash text
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON app.sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS app.consents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app.users(id),
  kind text NOT NULL CHECK (kind IN ('rules','privacy','telemetry','ai')),
  version text NOT NULL,
  accepted_at timestamptz NOT NULL DEFAULT now(),
  ip_hash text,
  UNIQUE (user_id, kind, version)
);

-- ============================================================ app: events & stages
CREATE TABLE IF NOT EXISTS app.events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES app.tenants(id),
  slug citext NOT NULL,
  name text NOT NULL,
  tz text NOT NULL DEFAULT 'Asia/Kolkata',
  starts_at timestamptz,
  ends_at timestamptz,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','live','ended','archived')),
  config jsonb NOT NULL DEFAULT '{}',
  config_revision int NOT NULL DEFAULT 0,
  paused boolean NOT NULL DEFAULT false,
  paused_at timestamptz,
  paused_total_s int NOT NULL DEFAULT 0,
  safe_mode boolean NOT NULL DEFAULT false,
  safe_mode_since timestamptz,
  published_at timestamptz,
  published_by uuid,
  finalized_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS app.stages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  stage_key text NOT NULL CHECK (stage_key ~ '^[a-z0-9_]{3,32}$'),   -- R-18
  ordinal int NOT NULL,
  name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('explain_only','flags','upload')),
  evaluator_kind text NOT NULL CHECK (evaluator_kind IN ('match_flags','run_tests','run_tests_and_docs')),
  explain_opens_at timestamptz,
  exec_opens_at timestamptz,
  exec_closes_at timestamptz,
  caps jsonb NOT NULL DEFAULT '{}',           -- max_span, max_reports_per_file, cooldowns, run limits
  run_commands jsonb NOT NULL DEFAULT '[]',  -- command_id allow-list with argv/env/timeout (B9)
  ai_share numeric(3,2) NOT NULL DEFAULT 0.40 CHECK (ai_share >= 0 AND ai_share <= 1),
  output_share numeric(3,2) NOT NULL DEFAULT 0.60,
  feedback_mode text NOT NULL DEFAULT 'hidden' CHECK (feedback_mode IN ('hidden','delayed','public')),
  UNIQUE (event_id, stage_key),
  UNIQUE (event_id, ordinal),
  CHECK (explain_opens_at IS NULL OR exec_opens_at IS NULL OR explain_opens_at <= exec_opens_at),
  CHECK (exec_opens_at IS NULL OR exec_closes_at IS NULL OR exec_opens_at < exec_closes_at),
  CHECK (ai_share + output_share = 1.00)
);

CREATE TABLE IF NOT EXISTS app.repo_options (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  key citext NOT NULL,
  title text NOT NULL,
  stack text,
  description_md text,
  readme_md text,
  challenge_id uuid,
  UNIQUE (event_id, key)
);

CREATE TABLE IF NOT EXISTS app.challenges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  kind text NOT NULL DEFAULT 'repo' CHECK (kind IN ('repo','bundle')),
  lifecycle text NOT NULL DEFAULT 'draft' CHECK (lifecycle IN ('draft','reviewed','frozen','sealed','published','archived')),
  manifest_hash text,
  manifest jsonb,
  images jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_challenge_per_option
  ON app.challenges (event_id, repo_option_id) WHERE lifecycle <> 'archived';

-- content blocks (Tier A/B per 07 §3.5)
CREATE TABLE IF NOT EXISTS app.content_blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  stage_id uuid REFERENCES app.stages(id),
  repo_option_id uuid REFERENCES app.repo_options(id),
  key text NOT NULL,
  body_md text NOT NULL,
  version int NOT NULL DEFAULT 1,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app.content_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_block_id uuid NOT NULL REFERENCES app.content_blocks(id),
  body_md text NOT NULL,
  changed_by uuid NOT NULL,
  changed_at timestamptz NOT NULL DEFAULT now(),
  approved_by uuid,
  approved_at timestamptz,
  announcement_draft_md text,
  published_at timestamptz
);

-- ============================================================ app: teams & progress
CREATE TABLE IF NOT EXISTS app.teams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  name text NOT NULL,
  quarantined boolean NOT NULL DEFAULT false,
  quarantine_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, name)
);

CREATE TABLE IF NOT EXISTS app.team_members (
  team_id uuid NOT NULL REFERENCES app.teams(id),
  user_id uuid NOT NULL REFERENCES app.users(id),
  role text NOT NULL CHECK (role IN ('lead','member')),
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_lead_per_team ON app.team_members (team_id) WHERE role = 'lead';

CREATE TABLE IF NOT EXISTS app.team_repo_choices (
  team_id uuid PRIMARY KEY REFERENCES app.teams(id),
  option_id uuid NOT NULL REFERENCES app.repo_options(id),
  locked_by uuid NOT NULL,
  locked_at timestamptz NOT NULL DEFAULT now(),
  override_by uuid,
  override_reason text
);

-- node pointer with sub-states (R-16/B11)
CREATE TYPE app.node AS ENUM (
  'LANDING','L1_EXPLAIN','L1_EXEC','L1_SUBMITTED',
  'L2_EXPLAIN','L2_EXEC','L2_SUBMITTED',
  'L3_EXPLAIN','L3_EXEC','L3_SUBMITTED',
  'L4_EXPLAIN','L4_EXEC','L4_SUBMITTED','DONE'
);
CREATE TYPE app.sub_state AS ENUM (
  'waiting_repo_lock','ready','active','submitting','evaluating','evaluated','adjusted'
);

CREATE TABLE IF NOT EXISTS app.participant_progress (
  participant_id uuid PRIMARY KEY REFERENCES app.users(id),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  node app.node NOT NULL DEFAULT 'LANDING',
  sub_state app.sub_state NOT NULL DEFAULT 'ready',
  stage_status jsonb NOT NULL DEFAULT '{}',
  adjusted_by uuid,
  adjusted_reason text,
  version int NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_progress_event_node ON app.participant_progress (event_id, node);

-- forward-only enforcement
CREATE OR REPLACE FUNCTION app.enforce_forward_node() RETURNS trigger AS $$
DECLARE
  rank_old int; rank_new int;
BEGIN
  SELECT enum_range(NULL::app.node)::text[] AS arr INTO rank_old;  -- placeholder, replaced below
  rank_old := array_position(enum_range(NULL::app.node), OLD.node);
  rank_new := array_position(enum_range(NULL::app.node), NEW.node);
  IF rank_new < rank_old THEN
    RAISE EXCEPTION 'node pointer cannot move backwards: % -> %', OLD.node, NEW.node
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_forward_node ON app.participant_progress;
CREATE TRIGGER trg_forward_node BEFORE UPDATE ON app.participant_progress
  FOR EACH ROW EXECUTE FUNCTION app.enforce_forward_node();

CREATE TABLE IF NOT EXISTS app.gate_hint (
  stage_id uuid NOT NULL REFERENCES app.stages(id),
  participant_id uuid NOT NULL REFERENCES app.users(id),
  allowed boolean NOT NULL,
  reason text,
  waiting_on jsonb,
  computed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (stage_id, participant_id)
);

-- ============================================================ app: drafts & submissions
CREATE TABLE IF NOT EXISTS app.drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  participant_id uuid NOT NULL REFERENCES app.users(id),
  stage_id uuid NOT NULL REFERENCES app.stages(id),
  version int NOT NULL DEFAULT 1,
  payload jsonb NOT NULL,
  base_version int,
  server_saved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (participant_id, stage_id)
);

CREATE TABLE IF NOT EXISTS app.submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  participant_id uuid NOT NULL REFERENCES app.users(id),
  team_id uuid REFERENCES app.teams(id),
  stage_id uuid NOT NULL REFERENCES app.stages(id),
  kind text NOT NULL CHECK (kind IN ('flags','upload')),
  status text NOT NULL DEFAULT 'received'
    CHECK (status IN ('received','validated','candidate_matched','auto_accept','needs_review',
                      'structural_reject','decided','ledgered','failed_retryable','failed_terminal','auto_submitted')),
  receipt_code text UNIQUE,
  accepted_at timestamptz,
  auto_submitted boolean NOT NULL DEFAULT false,
  artifacts_id uuid,
  rule_version text,
  config_hash text,
  evaluator_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (participant_id, stage_id)   -- one effective submission per participant per stage
);
CREATE INDEX IF NOT EXISTS idx_submissions_stage ON app.submissions (stage_id, accepted_at);

CREATE TABLE IF NOT EXISTS app.flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  submission_id uuid NOT NULL REFERENCES app.submissions(id) ON DELETE CASCADE,
  ordinal int NOT NULL,
  locations jsonb NOT NULL,               -- [{file, lines}]
  explanation text,
  category text,
  claimed_severity text,
  matched_award_unit_id uuid,
  match_confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flags_submission ON app.flags (submission_id);

CREATE TABLE IF NOT EXISTS app.submission_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  submission_id uuid REFERENCES app.submissions(id),
  sha256 text NOT NULL,
  size_bytes bigint NOT NULL,
  kind text NOT NULL CHECK (kind IN ('zip','diff','patch')),
  storage_key text NOT NULL,
  storage_kind text NOT NULL DEFAULT 'fs',
  validate_state text NOT NULL DEFAULT 'pending' CHECK (validate_state IN ('pending','stored','validating','ok','failed','deferred')),
  validate_problems jsonb
);

-- idempotency with route + retention (B4/R-15)
CREATE TABLE IF NOT EXISTS app.idempotency (
  participant_id uuid NOT NULL,
  route text NOT NULL,                    -- submit | repo_lock | upload | run | force_action | ...
  key text NOT NULL CHECK (char_length(key) BETWEEN 8 AND 128),
  payload_hash text NOT NULL,
  response_status int NOT NULL,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (participant_id, route, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON app.idempotency (expires_at);
-- correctness-critical routes keep event + 7 days; set by the prune job (JOB-14)

CREATE TABLE IF NOT EXISTS app.evaluation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid NOT NULL REFERENCES app.submissions(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('matcher','output','ai','manual','structural')),
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================ app: ledger & leaderboard (E.1/R-33)
CREATE TYPE app.component AS ENUM ('ai','output','manual');

CREATE TABLE IF NOT EXISTS app.ledger (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL,
  participant_id uuid NOT NULL,
  team_id uuid,
  stage_id uuid NOT NULL,
  award_unit_id uuid NOT NULL,
  component app.component NOT NULL,
  points numeric(10,2) NOT NULL,
  submission_id uuid,
  rule_version text,
  reversal_of uuid REFERENCES app.ledger(id),
  -- exactly-one-origin (R-33/E.1)
  gt_award_unit_id uuid,
  ap_entry_id uuid,
  manual_decision_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(gt_award_unit_id, ap_entry_id, manual_decision_id) = 1)
);
CREATE INDEX IF NOT EXISTS idx_ledger_team_stage ON app.ledger (team_id, stage_id);
CREATE INDEX IF NOT EXISTS idx_ledger_participant ON app.ledger (participant_id, stage_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_effective
  ON app.ledger (participant_id, stage_id, award_unit_id, component)
  WHERE reversal_of IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_reversal ON app.ledger (reversal_of)
  WHERE reversal_of IS NOT NULL;
-- team-level dedupe (D-02): one effective award per (team, stage, award_unit) across components is
-- enforced by ledger_claims; claims table is rebuildable from the ledger.

CREATE TABLE IF NOT EXISTS app.ledger_claims (
  team_id uuid NOT NULL,
  stage_id uuid NOT NULL,
  award_unit_id uuid NOT NULL,
  first_participant_id uuid NOT NULL,
  first_ledger_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, stage_id, award_unit_id)
);

CREATE TABLE IF NOT EXISTS app.leaderboard_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  version bigint NOT NULL,
  mode text NOT NULL DEFAULT 'frozen' CHECK (mode IN ('live','frozen','hidden')),
  payload jsonb NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, version)
);

-- state version tuple for /state ETag (R-09/B8)
CREATE TABLE IF NOT EXISTS app.state_versions (
  participant_id uuid NOT NULL REFERENCES app.users(id),
  event_id uuid NOT NULL,
  progress_version bigint NOT NULL DEFAULT 0,
  score_version bigint NOT NULL DEFAULT 0,
  flags_version bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (participant_id, event_id)
);

CREATE TABLE IF NOT EXISTS app.announcements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES app.events(id),
  severity text NOT NULL CHECK (severity IN ('info','warn','critical','emergency')),
  body_md text NOT NULL,
  audience jsonb NOT NULL DEFAULT '{"scope":"all"}',
  starts_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  retracted_at timestamptz,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_announcements_event ON app.announcements (event_id, starts_at);

-- ============================================================ app: jobs, outbox, quota, runs
CREATE TABLE IF NOT EXISTS app.jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  kind text NOT NULL,
  priority smallint NOT NULL DEFAULT 1,   -- 0 high, 1 normal, 2 low
  payload jsonb NOT NULL,
  dedupe_key text UNIQUE,
  run_at timestamptz NOT NULL DEFAULT now(),
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','leased','done','dead')),
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 5,
  leased_by text,
  leased_until timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jobs_poll ON app.jobs (state, run_at, priority);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON app.jobs (leased_until) WHERE state = 'leased';

CREATE TABLE IF NOT EXISTS app.outbox (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,
  target text,
  payload jsonb NOT NULL,
  attempts int NOT NULL DEFAULT 0,
  next_at timestamptz NOT NULL DEFAULT now(),
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','sent','failed','dead')),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_outbox_state ON app.outbox (state, next_at);

CREATE TABLE IF NOT EXISTS app.emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  to_addr text NOT NULL,
  subject text NOT NULL,
  body_text text,
  body_html text,
  state text NOT NULL DEFAULT 'pending',
  attempts int NOT NULL DEFAULT 0,
  sent_at timestamptz
);

CREATE TABLE IF NOT EXISTS app.quota (
  participant_id uuid PRIMARY KEY REFERENCES app.users(id),
  limits jsonb NOT NULL DEFAULT '{}',
  buckets jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  participant_id uuid NOT NULL REFERENCES app.users(id),
  stage_id uuid REFERENCES app.stages(id),
  kind text NOT NULL CHECK (kind IN ('practice','official')),
  command_id text,
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','running','finished','timed_out','killed','failed')),
  submission_id uuid,
  image_digest text,
  exit_code int,
  stdout text,
  stderr text,
  stdout_bytes bigint NOT NULL DEFAULT 0,
  truncated boolean NOT NULL DEFAULT false,
  killed_reason text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_runs_state ON app.runs (state, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_participant ON app.runs (participant_id, stage_id);

CREATE TABLE IF NOT EXISTS app.feature_flags (
  event_id uuid NOT NULL REFERENCES app.events(id),
  name text NOT NULL CHECK (name IN ('leaderboard','runner','ai','uploads','announcements','practice','read_only','admission_control','telemetry')),
  enabled boolean NOT NULL DEFAULT true,
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now(),
  reason text,
  PRIMARY KEY (event_id, name)
);

-- cache epoch: admin actions propagate to /state within ≤ 2 s (07 §3.9/BG-03)
CREATE TABLE IF NOT EXISTS app.cache_epoch (
  event_id uuid PRIMARY KEY REFERENCES app.events(id),
  epoch bigint NOT NULL DEFAULT 0
);

-- ============================================================ app: review, disputes, audit
CREATE TABLE IF NOT EXISTS app.review_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  submission_id uuid NOT NULL REFERENCES app.submissions(id),
  state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','assigned','decided')),
  assignee_id uuid,
  claimed_until timestamptz,
  priority int NOT NULL DEFAULT 1,
  due_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.review_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  queue_id uuid NOT NULL REFERENCES app.review_queue(id),
  reviewer_id uuid NOT NULL,
  decision text NOT NULL CHECK (decision IN ('accept_full','accept_partial','duplicate','invalid','unplanned_bug')),
  points numeric,
  reason text NOT NULL,
  ai_override boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.disputes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  participant_id uuid NOT NULL,
  subject_type text NOT NULL CHECK (subject_type IN ('award_unit','submission')),
  subject_id uuid NOT NULL,
  statement text NOT NULL,
  evidence jsonb,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','in_review','upheld','rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  decided_by uuid
);

-- append-only audit chain (revokes below)
CREATE TABLE IF NOT EXISTS audit.entries (
  id bigserial PRIMARY KEY,
  event_id uuid,
  actor_id uuid,
  actor_role text,
  action text NOT NULL,
  target_type text,
  target_id text,
  request_id text,
  before jsonb,
  after jsonb,
  details jsonb,
  prev_hash bytea,
  hash bytea,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit.entries (created_at DESC);

CREATE TABLE IF NOT EXISTS audit.checkpoints (
  id bigserial PRIMARY KEY,
  last_entry_id bigint NOT NULL,
  hash bytea NOT NULL,
  signed_blob bytea,
  storage_key text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================ app: admin & incident tables (T-2.7)
CREATE TABLE IF NOT EXISTS app.errors (
  id bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  request_id text,
  route text,
  error_code text,
  participant_id_hash text,
  message_redacted text,
  count_5m int NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app.admin_presence (
  admin_id uuid PRIMARY KEY REFERENCES app.users(id),
  last_seen timestamptz NOT NULL DEFAULT now(),
  current_route text
);

CREATE TABLE IF NOT EXISTS app.incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  severity text NOT NULL CHECK (severity IN ('sev1','sev2','sev3')),
  summary text NOT NULL,
  commander_id uuid,
  state text NOT NULL DEFAULT 'declared' CHECK (state IN ('declared','in_progress','resolved')),
  pir_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

CREATE TABLE IF NOT EXISTS app.incidents_timeline (
  id bigserial PRIMARY KEY,
  incident_id uuid NOT NULL REFERENCES app.incidents(id),
  note text NOT NULL,
  actor_id uuid,
  runbook_id text,
  step int,
  status text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.emergency_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  action text NOT NULL,
  params jsonb NOT NULL DEFAULT '{}',
  actor_id uuid NOT NULL,
  approver_id uuid,
  reason text NOT NULL CHECK (char_length(reason) >= 20),
  dry_run boolean NOT NULL DEFAULT false,
  confirmed_phrase text,
  undo_until timestamptz,
  undone_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_actions_rate ON app.emergency_actions (event_id, created_at);

CREATE TABLE IF NOT EXISTS app.ledger_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  label text,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.participant_freeze (
  participant_id uuid NOT NULL REFERENCES app.users(id),
  event_id uuid NOT NULL,
  frozen boolean NOT NULL DEFAULT true,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (participant_id, event_id)
);

CREATE TABLE IF NOT EXISTS app.ai_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid NOT NULL REFERENCES app.submissions(id),
  flag_id uuid REFERENCES app.flags(id),
  award_unit_id uuid,
  model text NOT NULL,
  model_version text NOT NULL,
  prompt_hash text NOT NULL,
  rubric_hash text NOT NULL,
  input_hash text NOT NULL,
  criteria_met jsonb NOT NULL,
  reasoning_chain_md text,
  evidence_quotes jsonb,
  model_confidence numeric,
  heuristic_confidence numeric,
  combined_confidence numeric,
  safety_flags jsonb NOT NULL DEFAULT '[]',
  review_required boolean NOT NULL DEFAULT false,
  raw_output jsonb,
  latency_ms int,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (submission_id, award_unit_id, prompt_hash, rubric_hash, model_version)  -- reuse on rescore (T-8.14)
);

CREATE TABLE IF NOT EXISTS app.ai_eval_sets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  award_unit_id uuid NOT NULL,
  label text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.ai_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES app.ai_assessments(id),
  criterion_id text NOT NULL,
  met boolean NOT NULL,
  reviewer_id uuid NOT NULL,
  reason text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,
  params jsonb NOT NULL DEFAULT '{}',
  state text NOT NULL DEFAULT 'pending',
  storage_key text,
  expires_at timestamptz,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================ gt schema (evaluator + restricted admin; R-03/E.1)
CREATE TABLE IF NOT EXISTS gt.bugs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL,
  repo_option_id uuid,
  award_unit_id uuid NOT NULL UNIQUE,
  canonical_file text NOT NULL,
  line_anchors jsonb NOT NULL,
  aliases jsonb NOT NULL DEFAULT '[]',
  category text,
  root_cause_group text,
  severity text,
  description_md text,
  canonical_patch_md text,
  reference_explanation_md text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt.hidden_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  award_unit_id uuid NOT NULL,
  language text NOT NULL,
  entrypoint text,
  stdin_b64 text,
  expected_stdout_b64 text,
  expected_stderr_b64 text,
  comparison_mode text NOT NULL DEFAULT 'exact' CHECK (comparison_mode IN ('exact','trimmed','json_structured','regex')),
  weight numeric NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt.rubrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  award_unit_id uuid NOT NULL,
  criteria jsonb NOT NULL,               -- [{id, description, weight}] weights sum to 1
  version int NOT NULL DEFAULT 1,
  hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt.official_images (
  award_unit_id uuid NOT NULL,
  language text NOT NULL,
  image_digest text NOT NULL,
  built_at timestamptz NOT NULL DEFAULT now(),
  source_sha text,
  PRIMARY KEY (award_unit_id, language)
);

-- ---- Answer Packs (E.1 verbatim + R-31 weight) ----
CREATE TABLE IF NOT EXISTS gt.answer_packs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  event_id uuid NOT NULL,
  challenge_id uuid NOT NULL,
  version int NOT NULL,
  state text NOT NULL CHECK (state IN ('draft','active','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid NOT NULL,
  activated_at timestamptz,
  activated_by uuid,
  approved_by uuid[],
  notes text,
  UNIQUE (event_id, challenge_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_pack ON gt.answer_packs (event_id, challenge_id) WHERE state = 'active';

CREATE TABLE IF NOT EXISTS gt.answer_pack_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  answer_pack_id uuid NOT NULL REFERENCES gt.answer_packs(id),
  award_unit_id uuid NOT NULL UNIQUE,
  canonical_file text NOT NULL,
  line_anchors jsonb NOT NULL,
  aliases jsonb NOT NULL DEFAULT '[]',
  category text,
  root_cause_group text,
  severity text,
  reference_explanation_md text,
  canonical_patch_md text,
  weight_multiplier numeric NOT NULL DEFAULT 1,     -- R-31
  origin text NOT NULL CHECK (origin IN ('unplanned','reviewer_override','rescore_correction')),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt.candidate_bugs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  submission_id uuid NOT NULL,
  flag_id uuid NOT NULL,
  reviewer_rationale text NOT NULL,
  state text NOT NULL CHECK (state IN ('pending','rejected','accepted')),
  decided_by uuid,
  decided_at timestamptz,
  decision_reason text,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt.answer_pack_links (
  answer_pack_entry_id uuid NOT NULL REFERENCES gt.answer_pack_entries(id),
  submission_id uuid NOT NULL,
  flag_id uuid NOT NULL,
  linked_by uuid NOT NULL,
  linked_at timestamptz NOT NULL DEFAULT now(),
  reason text NOT NULL,
  PRIMARY KEY (answer_pack_entry_id, submission_id, flag_id)
);

-- immutability: active/archived pack entries can never be updated or deleted (E.1)
CREATE OR REPLACE FUNCTION gt.ap_entries_immutable() RETURNS trigger AS $$
DECLARE pack_state text;
BEGIN
  SELECT state INTO pack_state FROM gt.answer_packs WHERE id = OLD.answer_pack_id;
  IF pack_state IN ('active','archived') THEN
    RAISE EXCEPTION 'answer_pack_entries of % packs are immutable', pack_state
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ap_entries_immutable ON gt.answer_pack_entries;
CREATE TRIGGER trg_ap_entries_immutable BEFORE UPDATE OR DELETE ON gt.answer_pack_entries
  FOR EACH ROW EXECUTE FUNCTION gt.ap_entries_immutable();

-- overlap guard: an AP entry may not overlap a GT bug anchor on the same file (R-32/E.1)
CREATE OR REPLACE FUNCTION gt.ap_no_overlap_gt() RETURNS trigger AS $$
DECLARE overlapping uuid;
BEGIN
  SELECT b.award_unit_id INTO overlapping
  FROM gt.bugs b
  WHERE b.canonical_file = NEW.canonical_file
    AND b.line_anchors::text <> '[]'
    AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(b.line_anchors) AS gt_anchor(cross)
      JOIN jsonb_array_elements(NEW.line_anchors) AS ap_anchor(cross)
        ON (gt_anchor->>'file' IS NOT DISTINCT FROM ap_anchor->>'file'
            OR NEW.canonical_file = b.canonical_file)
       AND ranges_overlap(gt_anchor->>'lines', ap_anchor->>'lines')
    )
  LIMIT 1;
  IF overlapping IS NOT NULL THEN
    RAISE EXCEPTION 'AP_OVERLAP_GT: entry overlaps ground-truth award unit %', overlapping
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ranges_overlap(min1-max1 text, min2-max2 text): tolerant ±2 lines not needed here; exact span overlap
CREATE OR REPLACE FUNCTION gt.ranges_overlap(a text, b text) RETURNS boolean AS $$
DECLARE a1 int; a2 int; b1 int; b2 int; dash int;
BEGIN
  dash := position('-' in a);
  a1 := split_part(CASE WHEN dash > 0 THEN left(a, dash-1) ELSE a END, '-', 1)::int;
  a2 := CASE WHEN dash > 0 THEN split_part(a, '-', 2)::int ELSE a1 END;
  dash := position('-' in b);
  b1 := split_part(CASE WHEN dash > 0 THEN left(b, dash-1) ELSE b END, '-', 1)::int;
  b2 := CASE WHEN dash > 0 THEN split_part(b, '-', 2)::int ELSE b1 END;
  RETURN (a1, a2 + 2) OVERLAPS (b1, b2 + 2);   -- ±2 line tolerance (02 §9.2)
END $$ LANGUAGE plpgsql IMMUTABLE;

DROP TRIGGER IF EXISTS trg_ap_no_overlap_gt ON gt.answer_pack_entries;
CREATE CONSTRAINT TRIGGER trg_ap_no_overlap_gt
  AFTER INSERT ON gt.answer_pack_entries
  DEFERRABLE INITIALLY IMMEDIATE
  FOR EACH ROW EXECUTE FUNCTION gt.ap_no_overlap_gt();

-- ============================================================ practice schema (PR-04 isolation)
CREATE TABLE IF NOT EXISTS practice.repos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  files jsonb NOT NULL,
  answer_key jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- practice uses its own IDs; no FK into app/gt (isolation invariant).

-- ============================================================ integrity schema
CREATE TABLE IF NOT EXISTS integrity.signals (
  id bigserial PRIMARY KEY,
  event_id uuid NOT NULL,
  participant_id uuid NOT NULL,
  kind text NOT NULL,      -- focus_loss | paste_length | concurrent_sessions | similarity | timing | cadence
  weight numeric NOT NULL DEFAULT 1,
  payload jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integrity.cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  participant_id uuid NOT NULL,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','dismissed','warned','penalized','escalated','disqualified')),
  notes jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================ ops schema
CREATE TABLE IF NOT EXISTS ops.health_snapshots (
  at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL,
  PRIMARY KEY (at)
);

-- ============================================================ grants (03 §1)
GRANT USAGE ON SCHEMA app TO app_api, admin_api, worker, evaluator, scheduler, runner_gw, auditor;
GRANT USAGE ON SCHEMA audit TO app_api, admin_api, worker, evaluator, scheduler, auditor;
GRANT USAGE ON SCHEMA gt TO evaluator, admin_api, gt_reader, auditor;
GRANT USAGE ON SCHEMA practice TO evaluator;
GRANT USAGE ON SCHEMA integrity TO admin_api, auditor;
GRANT USAGE ON SCHEMA ops TO admin_api;

-- app schema: CRUD for the API roles
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO app_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO admin_api;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO worker;
GRANT SELECT, INSERT, UPDATE ON app.submissions, app.evaluation_events, app.ledger, app.ledger_claims,
  app.runs, app.review_queue, app.ai_assessments, app.leaderboard_snapshots, app.state_versions, app.cache_epoch TO evaluator;
GRANT SELECT, INSERT, UPDATE ON app.jobs, app.stages, app.leaderboard_snapshots, app.quota, app.participant_progress,
  app.submissions, app.announcements, app.outbox TO scheduler;
GRANT SELECT, INSERT, UPDATE ON app.runs TO runner_gw;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO auditor;

-- audit: insert-only for app roles; read for auditor
GRANT INSERT ON audit.entries, audit.checkpoints TO app_api, admin_api, worker, evaluator, scheduler;
GRANT SELECT ON audit.entries, audit.checkpoints TO admin_api, auditor;

-- gt: evaluator read-only; admin writes via admin_api; gt_reader read-only.
-- app_api/worker/scheduler/runner_gw get NOTHING (R-03) — asserted by CI.
GRANT SELECT ON ALL TABLES IN SCHEMA gt TO evaluator, gt_reader, auditor;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA gt TO admin_api;

-- practice / integrity / ops
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA practice TO evaluator;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA integrity TO admin_api;
GRANT SELECT ON integrity.signals, integrity.cases TO auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO admin_api;

-- append-only enforcement: nobody may UPDATE/DELETE audit entries or ledger rows (03 §5)
REVOKE UPDATE, DELETE ON audit.entries FROM app_api, admin_api, worker, evaluator, scheduler;
REVOKE UPDATE, DELETE ON app.ledger FROM app_api, admin_api, worker, scheduler, runner_gw;
REVOKE UPDATE, DELETE ON app.evaluation_events FROM app_api, admin_api, worker, scheduler;

-- explicit GT denial for the roles that must never see it (CI asserts this too)
REVOKE ALL ON SCHEMA gt FROM app_api, worker, scheduler, runner_gw;
