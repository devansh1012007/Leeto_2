import { describe, expect, it } from "vitest";
import { validateReport, type ReportDraft } from "../../components/ReportPanel";

const base: ReportDraft = {
  file: "src/auth/session.py", lines: "41-47", category: "logic",
  title: "Non-constant-time comparison",
  description: "The code compares secrets with == which leaks timing information to attackers.",
  impact: "", evidence: "", suggestedFix: "",
};

describe("WS-04 field validation", () => {
  it("accepts a valid report", () => {
    expect(Object.keys(validateReport(base, 25))).toHaveLength(0);
  });
  it("rejects span over max", () => {
    expect(validateReport({ ...base, lines: "1-30" }, 25).lines).toContain("maximum");
  });
  it("rejects start > end", () => {
    expect(validateReport({ ...base, lines: "50-40" }, 25).lines).toBeTruthy();
  });
  it("rejects short description", () => {
    expect(validateReport({ ...base, description: "too short" }, 25).description).toBeTruthy();
  });
  it("rejects title out of range", () => {
    expect(validateReport({ ...base, title: "hi" }, 25).title).toBeTruthy();
  });
});
