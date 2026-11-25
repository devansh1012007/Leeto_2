/** Answer Authority console (C-97, 08 §2.3.4 + E.1–E.3): pack list, activation through
 * the approval flow returning rescore_job_id, AP↔GT overlap errors with links. */
import React, { useState } from "react";
import { ApprovalFlow, SensitiveBanner, TypedConfirm } from "../components/Rails";

interface PackEntry {
  id: string;
  award_unit_id: string;
  file: string;
  lines: string;
  origin: "unplanned" | "reviewer_override" | "rescore_correction";
  weight: number;
}

const PACKS = [
  { id: "v3", state: "active", activated_by: "Alice", entries: 21 },
  { id: "v2", state: "archived", activated_by: "Alice", entries: 20 },
  { id: "v4", state: "draft", activated_by: "—", entries: 22 },
];

const ENTRIES: PackEntry[] = [
  { id: "ape_1", award_unit_id: "apu_unplanned_1", file: "src/api/orders.py", lines: "88-96", origin: "unplanned", weight: 1 },
  { id: "ape_2", award_unit_id: "apu_unplanned_2", file: "src/util/parse.py", lines: "12-18", origin: "unplanned", weight: 1.5 },
];

export function AnswerAuthority(): React.JSX.Element {
  const [pack, setPack] = useState("v4");
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [rescoreJob, setRescoreJob] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  return (
    <main className="page answer-authority" data-testid="answer-authority">
      <SensitiveBanner frozen />
      <header className="aa-header">
        <h1>Answer Authority</h1>
        <span>Active pack: v3 (activated by Alice)</span>
      </header>

      <div className="aa-grid">
        <nav aria-label="Pack versions">
          <h3>Packs</h3>
          {PACKS.map((p) => (
            <button key={p.id} className={p.id === pack ? "active" : ""} onClick={() => setPack(p.id)}>
              {p.id} · {p.state} · {p.entries} entries
            </button>
          ))}
        </nav>

        <section className="aa-entries">
          <h3>Entries — {pack} (draft)</h3>
          {overlapError && (
            <p className="field-err" role="alert">
              AP_OVERLAP_GT: this entry overlaps a ground-truth anchor.{" "}
              <a href="#gt-compare">Compare with GT</a>
            </p>
          )}
          {rescoreJob && (
            <p className="result" role="status">Activated. Rescore job: <code>{rescoreJob}</code></p>
          )}
          <table>
            <thead><tr><th>Award unit</th><th>File</th><th>Lines</th><th>Origin</th><th>Weight</th></tr></thead>
            <tbody>
              {ENTRIES.map((e) => (
                <tr key={e.id}>
                  <td>{e.award_unit_id}</td><td>{e.file}</td><td>{e.lines}</td>
                  <td>{e.origin}</td><td>×{e.weight}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button
            className="ghost"
            onClick={() => setOverlapError("ape_3 overlaps gt anchor src/auth/session.py:12-16")}
          >
            Add entry (try an overlapping one)
          </button>
          {" "}
          <button className="ghost" onClick={() => setOverlapError(null)}>Add a clean entry</button>

          <h3>Activate {pack}</h3>
          <p className="hint">Activation never scores inline: it returns a rescore job (E.2). The announcement must not reveal the new bug location.</p>
          <label htmlFor="aa-reason">Reason (min 20 chars)</label>
          <textarea id="aa-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
          <ApprovalFlow
            actorId="admin-1"
            approvers={[{ id: "admin-1", name: "Me (blocked)" }, { id: "admin-2", name: "Bob" }]}
            onApprover={() => undefined}
            onSubmit={() => undefined}
          />
          <TypedConfirm
            onConfirm={() => setRescoreJob(`rescore_${pack}_job_001`)}
            disabled={reason.trim().length < 20}
          />
        </section>
      </div>
    </main>
  );
}
