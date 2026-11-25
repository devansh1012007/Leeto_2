// GENERATED from openapi/openapi.json — do not edit by hand.
// Regenerate: pnpm --filter api-client gen
export interface RequestOpts {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  token?: string;
  headers?: Record<string, string>;
}

export type TMeta = {
  /** Correlation id */
  "request_id": string;
  /** Authoritative server time (UTC) */
  "server_time": string /* RFC3339 */;
};

export type TErrorEnvelope = {
  "error": {
  /** Stable error code from openapi/errors.yaml */
  "code": string;
  /** Human-readable, safe to display (copy-catalog key resolved) */
  "message": string;
  /** Structured details per error code (e.g. waiting_on[], repo_choice, conflict) */
  "details"?: {

};
  "request_id": string;
};
};

export type TStageBrief = {
  /** Stable slug identity (R-18) */
  "stage_key": string;
  /** Informational order only */
  "ordinal": number;
  "name": string;
  "kind": "explain_only" | "flags" | "upload";
  "explain_opens_at"?: string /* RFC3339 */ | null;
  "exec_opens_at"?: string /* RFC3339 */ | null;
  "exec_closes_at"?: string /* RFC3339 */ | null;
  "state": "locked" | "open" | "closed";
  "paused"?: boolean;
  "submitted": boolean;
  "gate"?: {
  "allowed"?: boolean;
  "waiting_on"?: Array<string>;
  [k: string]: unknown;
};
};

/** state_shape_v1 (frozen, additive-only; see docs/CONTRACTS.md). ETag = sha256 of version tuple; server_time excluded from the ETag body. */
export type TState = {
  /** Always fresh; NOT part of the ETag body */
  "server_time": string /* RFC3339 */;
  "event": {
  "id": string;
  "status": "draft" | "published" | "live" | "ended" | "archived";
  "paused": boolean;
  "tz": string;
  "maintenance"?: boolean;
  /** Safe Mode master switch (08 §4.10) */
  "safe_mode"?: boolean;
  [k: string]: unknown;
};
  "me": {
  "participant_id": string;
  "team_id"?: string | null;
  "role": string;
  "consent_required": boolean;
  "min_client_version"?: string;
  [k: string]: unknown;
};
  "node_pointer": {
  "node": "LANDING" | "L1_EXPLAIN" | "L1_EXEC" | "L1_SUBMITTED" | "L2_EXPLAIN" | "L2_EXEC" | "L2_SUBMITTED" | "L3_EXPLAIN" | "L3_EXEC" | "L3_SUBMITTED" | "L4_EXPLAIN" | "L4_EXEC" | "L4_SUBMITTED" | "DONE";
  /** B11 sub-states */
  "sub_state": "waiting_repo_lock" | "ready" | "active" | "submitting" | "evaluating" | "evaluated" | "adjusted";
  "version": number;
  /** Set when an organizer force-advanced (R-23) */
  "adjusted_by"?: string | null;
  [k: string]: unknown;
};
  "stages": Array<TStageBrief>;
  "team": {
  "score": number;
  "score_version": number;
  "repo_choice": string | null;
  [k: string]: unknown;
};
  "versions": {
  "progress_version": number;
  "score_version": number;
  "leaderboard_version": number;
  "flags_version": number;
  "announcement_version": number;
  [k: string]: unknown;
};
  /** Latest 5; full list via GET /announcements */
  "announcements": Array<{
  "id": string;
  "severity": "info" | "warn" | "critical";
  "body_md": string;
  "created_at": string /* RFC3339 */;
  [k: string]: unknown;
}>;
  "feature_flags": {
  "leaderboard": boolean;
  "runner": boolean;
  "ai": boolean;
  "uploads": boolean;
  "announcements": boolean;
  "practice": boolean;
  "read_only": boolean;
  [k: string]: unknown;
};
};

export type TFlagInput = {
  /** Path within the team's repo option */
  "file": string;
  /** Line range like '41-47' or '41' */
  "lines": string;
  /** Why this is a defect */
  "explanation": string;
  "related"?: Array<{
  "file"?: string;
  "lines"?: string;
  [k: string]: unknown;
}>;
  "category"?: string;
  /** Optional reference to scratch files for official runs */
  "runnable_ref"?: string;
  [k: string]: unknown;
};

/** Discriminated union by kind (flags for levels 1-2, upload for levels 3-4). */
export type TSubmitRequest = {
  "kind": "flags";
  "flags": Array<TFlagInput>;
  [k: string]: unknown;
} | {
  "kind": "upload";
  /** Must have status=ok (or validation=deferred per B9) */
  "upload_id": string;
  [k: string]: unknown;
};

export type TSubmitAccepted = {
  /** Short receipt code (HMAC-derived) */
  "receipt_id": string;
  /** clock_timestamp() captured after the stage-state lock (B6) */
  "accepted_at": string /* RFC3339 */;
  "status"?: "received";
  [k: string]: unknown;
};

export type TRunRequest = {
  "stage_key": string;
  /** Must be in the stage's run_commands allow-list; fixed argv lives server-side (R-08/B9) */
  "command_id": string;
  /** Server draft reference, or a small inline delta */
  "workspace": {
  "draft_version": number;
  [k: string]: unknown;
} | {
  /** ≤ 256 KB inline delta */
  "delta": string;
  [k: string]: unknown;
};
  /** Optional base64 stdin */
  "stdin"?: string;
  /** Practice namespace; hidden inputs unreachable (06 §5) */
  "practice"?: boolean;
  [k: string]: unknown;
};

export type TRunState = {
  "id": string;
  "state": "queued" | "running" | "finished" | "timed_out" | "killed" | "failed";
  /** Capped; truncated flag set when over MAX_OUTPUT_BYTES */
  "stdout_b64"?: string;
  "stderr_b64"?: string;
  "exit_code"?: number | null;
  "truncated"?: boolean;
  /** Present while queued (admission control, 02 §10.5) */
  "queue_position"?: number;
  [k: string]: unknown;
};

export type TUpload = {
  "id": string;
  /** stored → validating → ok | failed (frozen lifecycle) */
  "status": "stored" | "validating" | "ok" | "failed";
  "sha256"?: string;
  "size"?: number;
  /** Present when failed (validation ran on the runner, never the API host) */
  "problems"?: Array<string>;
  [k: string]: unknown;
};

export type TDraftPut = {
  /** Workspace state; ≤ 512 KB serialized (else 413 DRAFT_TOO_LARGE) */
  "payload": {

};
  [k: string]: unknown;
};


export class ApiClient {
  private base: string;
  private fetchImpl: typeof fetch;
  private token?: string;
  private extraHeaders: Record<string, string>;

  constructor(opts: RequestOpts = {}) {
    this.base = (opts.baseUrl || "").replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl || globalThis.fetch.bind(globalThis);
    this.token = opts.token;
    this.extraHeaders = opts.headers || {};
  }

  setToken(token: string | undefined): void {
    this.token = token;
  }

  private async request(path: string, init: { method: string; body?: unknown; headers?: Record<string, string> }): Promise<unknown> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Client-Version": "1.0.0",
      ...this.extraHeaders,
      ...(init.headers || {}),
    };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const res = await this.fetchImpl(this.base + path, {
      method: init.method,
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
    if (res.status === 304) return null;
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const err = (json && (json as { error?: { code?: string } }).error) || {};
      throw new ApiError(err.code || "INTERNAL", err.message || res.statusText, res.status);
    }
    return json;
  }

  /** Sign in */
  async post_v1_auth_login(body: {
  /** email or username */
  "identifier": string;
  "password": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/login`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }

  /** Rotate refresh token */
  async post_v1_auth_refresh(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/refresh`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Revoke session */
  async post_v1_auth_logout(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/logout`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Activate account via invite */
  async post_v1_auth_activate(Idempotency_Key: string | undefined, body: {
  "token": string;
  "password": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/activate`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Request password reset (always generic) */
  async post_v1_auth_reset_request(Idempotency_Key: string | undefined, body: {
  "email": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/reset/request`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Confirm reset */
  async post_v1_auth_reset_confirm(Idempotency_Key: string | undefined, body: {
  "token": string;
  "password": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/auth/reset/confirm`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Profile, roles, consent state */
  async get_v1_me(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/me`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Consent versions and state */
  async get_v1_consent(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/consent`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Accept rules/privacy versions */
  async post_v1_consent(Idempotency_Key: string | undefined, body: {
  "versions": {

};
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/consent`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Public event metadata (cacheable 30s) */
  async get_v1_event_public(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/event/public`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Sanitized event details markdown */
  async get_v1_content_event_details(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/content/event-details`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Server time for offset estimation */
  async get_v1_time(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/time`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Authoritative aggregated state (state_shape_v1; ETag from version tuple) */
  async get_v1_state(If_None_Match: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/state`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      headers: { ...optHeaders, "If-None-Match": String(If_None_Match) },
      });
  }

  /** Node states + deadlines (progress bar) */
  async get_v1_progress(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/progress`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Leaderboard snapshot (mode-aware) */
  async get_v1_leaderboard(since: number | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/leaderboard`;
    const qs = new URLSearchParams();
    if (since !== undefined) qs.set("since", String(since));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Team members and status */
  async get_v1_team(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/team`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Team score + version */
  async get_v1_team_score(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/team/score`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Announcements (paginated) */
  async get_v1_announcements(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/announcements`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Team's repo option tree (watermarked) */
  async get_v1_repo_tree(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/repo/tree`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Watermarked file content (no-store) */
  async get_v1_repo_files__path_(path: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/repo/files/${path}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Server-side repo search (20/min) */
  async get_v1_repo_search(q: string | undefined, cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/repo/search`;
    const qs = new URLSearchParams();
    if (q !== undefined) qs.set("q", String(q));
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Current repo choice or null */
  async get_v1_team_repo_lock(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/team/repo-lock`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Lock repo choice (lead only, once) */
  async post_v1_team_repo_lock(Idempotency_Key: string | undefined, body: {
  "option": string;
  "confirm": true;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/team/repo-lock`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Gate check (recomputed live, hint ≤ 2 s stale) */
  async get_v1_stages__stage_key__gate(stage_key: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/stages/${stage_key}/gate`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Latest server draft */
  async get_v1_drafts__stage_key_(stage_key: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/drafts/${stage_key}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Save draft (If-Match optimistic concurrency; 3-way merge) */
  async put_v1_drafts__stage_key_(stage_key: string, If_Match: string | undefined, body: TDraftPut, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/drafts/${stage_key}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "PUT",
      headers: { ...optHeaders, "If-Match": String(If_Match) },
      body,
      });
  }

  /** Submit stage (discriminated flags|upload) */
  async post_v1_stages__stage_key__submit(stage_key: string, Idempotency_Key: string | undefined, body: TSubmitRequest, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/stages/${stage_key}/submit`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Upload artifact (stored; validation is a runner job) */
  async post_v1_uploads(Idempotency_Key: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/uploads`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      });
  }

  /** Enqueue upload validation (202 job) */
  async post_v1_uploads__id__validate(id: string, Idempotency_Key: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/uploads/${id}/validate`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      });
  }

  /** Upload status */
  async get_v1_uploads__id_(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/uploads/${id}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Delete upload (before submit only) */
  async delete_v1_uploads__id_(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/uploads/${id}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "DELETE",
      });
  }

  /** Create run (allow-listed command_id; concurrency 1) */
  async post_v1_runs(Idempotency_Key: string | undefined, body: TRunRequest, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/runs`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Run state/output */
  async get_v1_runs__id_(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/runs/${id}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Cancel run */
  async post_v1_runs__id__cancel(id: string, Idempotency_Key: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/runs/${id}/cancel`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      });
  }

  /** Submission receipt */
  async get_v1_receipts__id_(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/receipts/${id}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Own results (post-finalization only) */
  async get_v1_results(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/results`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** File a dispute (within appeal window) */
  async post_v1_disputes(Idempotency_Key: string | undefined, body: {
  "subject_type": "award_unit" | "submission";
  "subject_id": string;
  "statement": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/disputes`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Own disputes */
  async get_v1_disputes(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/disputes`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Runtime client config (client version, flags, min version) */
  async get_v1_config_json(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/config.json`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Practice state (separate namespace) */
  async get_v1_practice_state(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/practice/state`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Practice file content */
  async get_v1_practice_files__path_(path: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/practice/files/${path}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Practice run (sample inputs only; never hidden inputs) */
  async post_v1_practice_runs(Idempotency_Key: string | undefined, body: {
  "language": string;
  "entrypoint"?: string;
  "files": Array<{

}>;
  "stdin"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/practice/runs`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Liveness */
  async get_healthz(opts?: RequestOpts): Promise<unknown> {
    let url = `/healthz`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Readiness (DB, schema head, clock < 100ms, disk) */
  async get_readyz(opts?: RequestOpts): Promise<unknown> {
    let url = `/readyz`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Prometheus metrics (internal network only, never Tunnel-routed) */
  async get_metrics(opts?: RequestOpts): Promise<unknown> {
    let url = `/metrics`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Step-up re-auth (valid 5 min) */
  async post_v1_admin_auth_step_up(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/auth/step-up`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Admin logout */
  async post_v1_admin_auth_logout(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/auth/logout`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Events list */
  async get_v1_admin_events(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Create event */
  async post_v1_admin_events(Idempotency_Key: string | undefined, body: {
  "name": string;
  "slug": string;
  "tz": string;
  /** Hard cap; N is parametric (R-01/D-25) */
  "capacity"?: number;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Publish event (freezes config) */
  async post_v1_admin_events__id__publish(id: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/publish`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Pause event (reason required) */
  async post_v1_admin_events__id__pause(id: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/pause`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Resume event */
  async post_v1_admin_events__id__resume(id: string, Idempotency_Key: string | undefined, body: {
  "reason"?: string;
  /** Auto-adjust deadline by paused duration or custom */
  "shift_deadline_by_s"?: number;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/resume`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Extend stage */
  async post_v1_admin_stages__id__extend(id: string, Idempotency_Key: string | undefined, body: {
  "minutes": number;
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/stages/${id}/extend`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Kill switches state */
  async get_v1_admin_events__id__switches(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/switches`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Flip a kill switch */
  async post_v1_admin_events__id__switches(id: string, Idempotency_Key: string | undefined, body: {
  "name": "leaderboard" | "runner" | "ai" | "uploads" | "announcements" | "practice" | "read_only" | "admission_control";
  "enabled": boolean;
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/switches`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Live console aggregate (no per-participant rows) */
  async get_v1_admin_events__id__live(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/live`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Create announcement */
  async post_v1_admin_events__id__announcements(id: string, Idempotency_Key: string | undefined, body: {
  "severity": "info" | "warn" | "critical" | "emergency";
  "body_md": string;
  "audience"?: {

};
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/announcements`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Force-advance team (auto-submits pending level first) */
  async post_v1_admin_events__id__teams__tid__advance(id: string, tid: string, Idempotency_Key: string | undefined, body: {
  "to_node": string;
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/teams/${tid}/advance`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Read-only participant state (admin preview, no impersonation) */
  async get_v1_admin_participants__pid__state(pid: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/participants/${pid}/state`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Effect preview for a proposed action */
  async post_v1_admin_preview_effect(body: {
  "action": string;
  "payload": {

};
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/preview/effect`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }

  /** Challenges list */
  async get_v1_admin_challenges(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Create/upload challenge (validated; inert blobs) */
  async post_v1_admin_challenges(Idempotency_Key: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      });
  }

  /** Ground truth (step-up; audited; sensitive banner) */
  async get_v1_admin_challenges__id__ground_truth(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges/${id}/ground-truth`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Edit GT pre-freeze only (post-freeze → new revision + rescore) */
  async put_v1_admin_challenges__id__ground_truth(id: string, Idempotency_Key: string | undefined, body: {
  "bugs"?: Array<{

}>;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges/${id}/ground-truth`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "PUT",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** List answer packs */
  async get_v1_admin_challenges__id__answer_packs(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges/${id}/answer-packs`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Create pack from current GT (draft, in gt schema) */
  async post_v1_admin_challenges__id__answer_packs(id: string, Idempotency_Key: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges/${id}/answer-packs`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      });
  }

  /** Activate pack (ground_truth + step-up + two approvers; returns rescore_job_id; NEVER scores inline) */
  async post_v1_admin_answer_packs__id__activate(id: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  /** Second approver; must differ from actor */
  "approver_id": string;
  /** Must not reveal the new bug's location */
  "announcement_draft_md"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/answer-packs/${id}/activate`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Add entry (origin=unplanned; draft; overlap → AP_OVERLAP_GT) */
  async post_v1_admin_answer_packs__id__entries(id: string, Idempotency_Key: string | undefined, body: {
  "canonical_file": string;
  "line_anchors": Array<{

}>;
  "aliases"?: Array<unknown>;
  "category"?: string;
  /** R-31 per-bug weight */
  "weight_multiplier"?: number;
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/answer-packs/${id}/entries`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Link a report to an AP entry (writes ledger ap_entry_id) */
  async post_v1_admin_answer_packs__id__entries__eid__link(id: string, eid: string, Idempotency_Key: string | undefined, body: {
  "submission_id": string;
  "flag_id": string;
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/answer-packs/${id}/entries/${eid}/link`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Candidate bug queue */
  async get_v1_admin_challenges__id__candidate_bugs(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/challenges/${id}/candidate-bugs`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Accept as draft AP entry (no scoring yet) */
  async post_v1_admin_candidate_bugs__cid__accept(cid: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/candidate-bugs/${cid}/accept`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Reject candidate (reason) */
  async post_v1_admin_candidate_bugs__cid__reject(cid: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/candidate-bugs/${cid}/reject`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Rescore dry-run (byte-identical to execute; no writes) */
  async post_v1_admin_events__id__rescore_dry_run(id: string, body: {
  "pack_id"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/rescore/dry-run`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }

  /** Execute rescore (step-up + two approvers + typed RESCORE) */
  async post_v1_admin_events__id__rescore_execute(id: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  "approver_id": string;
  /** Typed confirmation (R-34) */
  "confirm": "RESCORE";
  "dry_run_id"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/rescore/execute`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Leaderboard mode live|frozen|hidden */
  async post_v1_admin_events__id__leaderboard_mode(id: string, Idempotency_Key: string | undefined, body: {
  "mode": "live" | "frozen" | "hidden";
  "reason": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/leaderboard/mode`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Finalize (checklist; step-up; irreversible) */
  async post_v1_admin_events__id__finalize(id: string, Idempotency_Key: string | undefined, body: {
  "confirm": "FINALIZE";
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/finalize`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Review queue */
  async get_v1_admin_review_queue(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/review/queue`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Claim (exclusive 15 min) */
  async post_v1_admin_review__id__claim(id: string, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/review/${id}/claim`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Decide (reason required; writes ledger) */
  async post_v1_admin_review__id__decide(id: string, Idempotency_Key: string | undefined, body: {
  "decision": "accept_full" | "accept_partial" | "duplicate" | "invalid" | "unplanned_bug";
  "reason": string;
  "points"?: number;
  "ai_override"?: boolean;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/review/${id}/decide`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Disputes inbox */
  async get_v1_admin_disputes(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/disputes`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Emergency action (all rails enforced) */
  async post_v1_admin_events__id__emergency__action_(id: string, action: string, Idempotency_Key: string | undefined, body: {
  "reason": string;
  /** Typed numeral e.g. '7' (R-34) */
  "confirm": string;
  "approver_id"?: string;
  "dry_run"?: boolean;
  "payload"?: {

};
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/events/${id}/emergency/${action}`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Declare incident */
  async post_v1_admin_incidents(Idempotency_Key: string | undefined, body: {
  "severity": "sev1" | "sev2" | "sev3";
  "summary": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/incidents`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Update incident (timeline) */
  async post_v1_admin_incidents__iid__update(iid: string, Idempotency_Key: string | undefined, body: {
  "note": string;
  "status"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/incidents/${iid}/update`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Resolve (auto-drafts PIR) */
  async post_v1_admin_incidents__iid__resolve(iid: string, Idempotency_Key: string | undefined, body: {
  "resolution": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/incidents/${iid}/resolve`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Assign incident commander */
  async post_v1_admin_incidents__iid__assign(iid: string, Idempotency_Key: string | undefined, body: {
  "commander_id": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/incidents/${iid}/assign`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** Record runbook step done */
  async post_v1_admin_incidents__iid__step(iid: string, Idempotency_Key: string | undefined, body: {
  "runbook_id": string;
  "step": number;
  "status": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/incidents/${iid}/step`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** User accounts (tenant-scoped) */
  async get_v1_admin_users(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/users`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Audit search (chain verify status included) */
  async get_v1_admin_audit(cursor: string | undefined, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/audit`;
    const qs = new URLSearchParams();
    if (cursor !== undefined) qs.set("cursor", String(cursor));
    url += "?" + qs.toString();
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Verify audit chain */
  async post_v1_admin_audit_verify(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/audit/verify`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      });
  }

  /** Request export (background job; expiring link) */
  async post_v1_admin_exports(Idempotency_Key: string | undefined, body: {
  "kind": string;
  "params"?: {

};
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/exports`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      headers: { ...optHeaders, "Idempotency-Key": String(Idempotency_Key) },
      body,
      });
  }

  /** System health aggregate */
  async get_v1_admin_health(opts?: RequestOpts): Promise<unknown> {
    let url = `/v1/admin/health`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "GET",
      });
  }

  /** Runner pulls a job (mutual TLS / signed per-runner token) */
  async post_runner_claim(body: {
  "runner_id": string;
  "capacity": number;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/runner/claim`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }

  /** Heartbeat (response may cancel) */
  async post_runner_jobs__id__heartbeat(id: string, body: {
  "state": string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/runner/jobs/${id}/heartbeat`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }

  /** Report result (untrusted; gateway validates schema/size) */
  async post_runner_jobs__id__result(id: string, body: {
  "state": "finished" | "timed_out" | "killed" | "failed";
  "exit_code"?: number;
  "stdout"?: string;
  "stderr"?: string;
  "usage"?: {

};
  "started_at"?: string /* RFC3339 */;
  "finished_at"?: string /* RFC3339 */;
  "sandbox_fault"?: string;
  [k: string]: unknown;
}, opts?: RequestOpts): Promise<unknown> {
    let url = `/runner/jobs/${id}/result`;
    
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "POST",
      body,
      });
  }
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  constructor(code: string, message: string, status: number) {
    super(`[${code}] ${message}`);
    this.code = code;
    this.status = status;
  }
}
