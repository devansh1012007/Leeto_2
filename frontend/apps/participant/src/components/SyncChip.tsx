/**
 * Sync chip (T-5.4, 02 §2.6 + 07 §5.4.4): exactly five states.
 * A queued submit is NEVER displayed as accepted (R-27).
 */
import React from "react";

export type SyncState =
  | "saved_locally"
  | "saved_to_server"
  | "offline_kept"
  | "submit_queued"
  | "submission_accepted";

export const SYNC_LABELS: Record<SyncState, string> = {
  saved_locally: "Saved locally",
  saved_to_server: "Saved to server",
  offline_kept: "Offline: changes kept on this device",
  submit_queued: "Submit queued, not accepted yet",
  submission_accepted: "Submission accepted",
};

export function SyncChip({ state }: { state: SyncState }): React.JSX.Element {
  const cls =
    state === "submission_accepted" ? "chip accepted"
    : state === "submit_queued" || state === "offline_kept" ? "chip warn"
    : "chip";
  return (
    <span className={cls} role="status" aria-live="polite" data-testid="sync-chip">
      {SYNC_LABELS[state]}
    </span>
  );
}

/** Never show accepted unless the server returned 2xx (R-27). */
export function deriveSyncState(params: {
  offline: boolean;
  outboxSize: number;
  serverSavedAt: number | null;
  lastSubmitAccepted: boolean;
}): SyncState {
  if (params.lastSubmitAccepted) return "submission_accepted";
  if (params.outboxSize > 0) return params.offline ? "offline_kept" : "submit_queued";
  if (params.serverSavedAt !== null) return "saved_to_server";
  return "saved_locally";
}
