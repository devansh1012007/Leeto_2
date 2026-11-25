import { describe, expect, it } from "vitest";
import { deriveSyncState, SYNC_LABELS } from "../../components/SyncChip";

describe("sync chip (T-5.4, R-27)", () => {
  it("has exactly the five states", () => {
    expect(Object.keys(SYNC_LABELS)).toHaveLength(5);
  });

  it("never shows accepted without a server 2xx", () => {
    expect(deriveSyncState({ offline: false, outboxSize: 1, serverSavedAt: 1, lastSubmitAccepted: false }))
      .toBe("submit_queued");
    expect(deriveSyncState({ offline: true, outboxSize: 2, serverSavedAt: 1, lastSubmitAccepted: false }))
      .toBe("offline_kept");
  });

  it("accepted wins over queued", () => {
    expect(deriveSyncState({ offline: true, outboxSize: 3, serverSavedAt: 1, lastSubmitAccepted: true }))
      .toBe("submission_accepted");
  });

  it("falls back through server-saved to local", () => {
    expect(deriveSyncState({ offline: false, outboxSize: 0, serverSavedAt: 5, lastSubmitAccepted: false }))
      .toBe("saved_to_server");
    expect(deriveSyncState({ offline: false, outboxSize: 0, serverSavedAt: null, lastSubmitAccepted: false }))
      .toBe("saved_locally");
  });
});
