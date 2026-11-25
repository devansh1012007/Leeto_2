/** Emergency control room (08 §4.1): red-and-black, every action through the rails. */
import React, { useState } from "react";
import { EffectPreview, TypedConfirm, type EffectPreviewData } from "../components/Rails";

const CATEGORIES: { key: string; label: string; actions: string[] }[] = [
  { key: "availability", label: "Availability", actions: ["pause", "resume", "extend", "safe_mode"] },
  { key: "participants", label: "Participants", actions: ["freeze_participants", "kill_sessions", "logout_all", "quarantine"] },
  { key: "scoring", label: "Scoring", actions: ["score_adjust", "snapshot", "restore", "publish_partial"] },
  { key: "infrastructure", label: "Infrastructure", actions: ["drain_runner", "kill_runs", "state_lite", "cache_reset"] },
];

const CATALOG: Record<string, string> = {
  pause: "The event is paused. The clock is stopped. Please wait for the resume announcement.",
  resume: "The round resumed; the countdown continues",
  extend: "The deadline for this level was extended by {minutes} minutes.",
  safe_mode: "The platform is operating in Safe Mode. Your work is saved locally and will sync when normal operation resumes.",
  freeze_participants: "Your account is temporarily frozen; you can view but not submit.",
  kill_sessions: "Your sessions were ended for security reasons. Please sign in again.",
  logout_all: "Please sign in again",
  quarantine: "Under review — work continues, submissions held",
  score_adjust: "Scores were adjusted after review; see your results page.",
  snapshot: "",
  restore: "Scores were corrected after a platform issue. Check your results page for the updated breakdown.",
  publish_partial: "Partial results are now available on the results page.",
  drain_runner: "",
  kill_runs: "All in-flight code runs were cancelled. Your reports are unaffected.",
  state_lite: "",
  cache_reset: "",
};

const UNDO: Record<string, string> = {
  pause: "Resume within 4 h", resume: "No undo", extend: "Undo available for 60 s",
  safe_mode: "Exit (auto-exit after 4 h)", freeze_participants: "Reversible",
  kill_sessions: "No undo", logout_all: "No undo (extremely disruptive)", quarantine: "Un-quarantine",
  score_adjust: "Reversal ledger entries only", snapshot: "n/a", restore: "Reversal entries only",
  publish_partial: "Unpublish (ledger intact)", drain_runner: "Reversible", kill_runs: "No undo",
  state_lite: "Reversible", cache_reset: "n/a",
};

export function EmergencyRoom(): React.JSX.Element {
  const [action, setAction] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [preview, setPreview] = useState<EffectPreviewData | null>(null);
  const [result, setResult] = useState<string | null>(null);

  function select(next: string) {
    setAction(next);
    setPreview({
      participantCopy: CATALOG[next] ? [CATALOG[next]] : [],
      scope: "all participants",
      duration: next === "pause" ? "until resumed" : "immediate",
      undo: UNDO[next] ?? "No undo",
    });
    setResult(null);
  }

  return (
    <main className="page emergency-room" data-testid="emergency-room">
      <div className="er-banner" role="alert">EMERGENCY CONTROL ROOM — actions are audited</div>
      <div className="er-grid">
        <nav className="er-rail" aria-label="Categories">
          {CATEGORIES.map((c) => (
            <section key={c.key}>
              <h3>{c.label}</h3>
              {c.actions.map((a) => (
                <button key={a} className={a === action ? "active" : ""} onClick={() => select(a)}>
                  {a.replace(/_/g, " ")}
                </button>
              ))}
            </section>
          ))}
        </nav>
        <section className="er-action">
          {!action && <p className="hint">Select an action. Every action requires step-up, a reason, typed confirmation, and (for destructive scope) a second approver.</p>}
          {action && (
            <>
              <h2>{action.replace(/_/g, " ")}</h2>
              <EffectPreview data={preview} />
              <label htmlFor="er-reason">Reason (min 20 characters — persisted to audit, incident timeline, PIR)</label>
              <textarea id="er-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
              <label>
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} /> Dry run first (no side effects)
              </label>
              <TypedConfirm onConfirm={() => setResult(dryRun ? "Dry run complete — no side effects. Review the preview above." : `Executed ${action}.`)} disabled={reason.trim().length < 20} />
              {result && <p className="result" role="status">{result}</p>}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
