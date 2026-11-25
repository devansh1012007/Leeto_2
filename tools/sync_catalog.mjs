// Copy copy/catalog.yaml into participant src, FILTERED to participant-visible keys only
// (T-5.11: the participant bundle must contain zero admin strings / zero gt content).
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(join(root, "copy", "catalog.yaml"), "utf8");

// Admin-only error codes never ship to participants (openapi errors.yaml is server-side).
const ADMIN_ONLY_ERROR_CODES = new Set([
  "AP_OVERLAP_GT", "ESCALATION_REQUIRED", "EMERGENCY_RATE_LIMITED", "TIMING_GUARD",
  "AUTH_STEP_UP_REQUIRED",
]);

const outLines = [];
for (const line of src.split("\n")) {
  const m = /^([^: ]+):\s*"(.*)"\s*$/.exec(line.trim());
  if (!m) { outLines.push(line); continue; }
  const key = m[1];
  if (key.startsWith("admin.") || key.startsWith("emergency.")) continue;      // admin-side copy
  if (ADMIN_ONLY_ERROR_CODES.has(key.replace("error.", "")) && key.startsWith("error.")) continue;
  outLines.push(line);
}

const dest = join(root, "frontend", "apps", "participant", "src", "catalog.gen.yaml");
mkdirSync(dirname(dest), { recursive: true });
writeFileSync(dest, outLines.join("\n"), "utf8");
console.log("participant catalog synced (filtered):", outLines.filter((l) => l.includes(": \"")).length, "keys");
