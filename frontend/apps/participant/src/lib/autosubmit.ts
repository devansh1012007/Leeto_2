/**
 * Auto-submit flow (T-5.6, 07 §5.4.4): warnings at 5/3/1 min; at 0 a blocking modal,
 * flush via sendBeacon, poll /state at 1 s until the pointer advances; after 60 s show
 * the request_id + safe-close message.
 */
import type { ApiClient } from "@bhctf/api-client";

// generated client method names follow `method_v1_path` from the OpenAPI operationIds
type StateGetter = Pick<ApiClient, "get_v1_state">;

export type AutoSubmitPhase = "armed" | "warn_5m" | "warn_3m" | "warn_1m" | "submitting" | "confirming" | "timeout_help";

export interface AutoSubmitState {
  phase: AutoSubmitPhase;
  requestId: string;
}

export function nextWarning(secondsLeft: number): AutoSubmitPhase | null {
  if (secondsLeft <= 60) return "warn_1m";
  if (secondsLeft <= 180) return "warn_3m";
  if (secondsLeft <= 300) return "warn_5m";
  return null;
}

/** Flush the draft via sendBeacon (survives tab close) — WS-11 grace behavior. */
export function flushViaBeacon(url: string, payload: unknown): boolean {
  const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
  return navigator.sendBeacon?.(url, blob) ?? false;
}

/** Poll /state once per second until the node pointer advances past the stage. */
export async function waitForPointerAdvance(
  client: StateGetter,
  opts: { fromNode: string; timeoutMs?: number; intervalMs?: number },
): Promise<{ advanced: boolean; requestId: string; waitedMs: number }> {
  const started = Date.now();
  const timeoutMs = opts.timeoutMs ?? 60000;
  let lastRequestId = "-";
  while (Date.now() - started < timeoutMs) {
    try {
      const res = (await client.get_v1_state(undefined)) as
        | { data?: { node_pointer?: { node?: string } }; meta?: { request_id?: string } }
        | null;
      const node = res?.data?.node_pointer?.node;
      lastRequestId = res?.meta?.request_id ?? lastRequestId;
      if (node && node !== opts.fromNode && !node.endsWith("EXEC")) {
        return { advanced: true, requestId: lastRequestId, waitedMs: Date.now() - started };
      }
    } catch {
      // transient poll failure — keep polling until the timeout (fail closed, keep trying)
    }
    await new Promise((r) => setTimeout(r, opts.intervalMs ?? 1000));
  }
  return { advanced: false, requestId: lastRequestId, waitedMs: Date.now() - started };
}
