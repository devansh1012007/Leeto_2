import { describe, expect, it } from "vitest";
import { nextWarning } from "../../lib/autosubmit";

describe("auto-submit warnings (T-5.6)", () => {
  it("warns at 5/3/1 minutes", () => {
    expect(nextWarning(400)).toBeNull();
    expect(nextWarning(290)).toBe("warn_5m");
    expect(nextWarning(170)).toBe("warn_3m");
    expect(nextWarning(50)).toBe("warn_1m");
  });
});
