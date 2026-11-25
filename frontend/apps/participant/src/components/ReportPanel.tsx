/** Report panel (WS-04): field-level validation, caps display, duplicate-area note,
 * no HTML rendering of user text, paste-length counter (advisory). */
import React, { useMemo, useState } from "react";

export interface ReportDraft {
  file: string;
  lines: string;
  category: string;
  title: string;
  description: string;
  impact: string;
  evidence: string;
  suggestedFix: string;
}

const CATEGORIES = [
  "logic", "input_validation", "authentication_authorization", "injection", "cryptography",
  "resource_handling", "concurrency", "error_handling", "configuration", "integration_api_contract",
  "data_handling", "other",
];

export function validateReport(d: ReportDraft, maxSpan: number): Record<string, string> {
  const errs: Record<string, string> = {};
  if (!d.file.trim()) errs.file = "Target file is required";
  const m = /^(\d+)(?:-(\d+))?$/.exec(d.lines.trim());
  if (!m) {
    errs.lines = "Use 'start' or 'start-end'";
  } else {
    const start = Number(m[1]);
    const end = Number(m[2] ?? m[1]);
    if (start > end) errs.lines = "start must be ≤ end";
    else if (end - start + 1 > maxSpan) errs.lines = `Line span exceeds the maximum (${maxSpan})`;
  }
  if (d.title.trim().length < 5 || d.title.trim().length > 120) errs.title = "5–120 characters";
  if (d.description.trim().length < 40 || d.description.trim().length > 2000)
    errs.description = "40–2000 characters; explain the defect and why it is wrong";
  if (d.impact.length > 500) errs.impact = "≤ 500 characters";
  if (d.suggestedFix.length > 500) errs.suggestedFix = "≤ 500 characters";
  return errs;
}

export function ReportPanel(props: {
  draft: ReportDraft;
  onChange: (d: ReportDraft) => void;
  onSubmit: () => void;
  maxSpan: number;
  reportsLeft: number;
  alreadyReportedArea: boolean;
  requireEvidence: boolean;
  pasteEvents: number;
}): React.JSX.Element {
  const errs = useMemo(() => validateReport(props.draft, props.maxSpan), [props.draft, props.maxSpan]);
  const valid = Object.keys(errs).length === 0;
  const evidenceErr =
    props.requireEvidence && props.draft.evidence.trim().length < 40 ? "Reproduction/evidence is required (min 40 chars)" : "";

  return (
    <section className="panel report-panel" aria-labelledby="report-title">
      <h2 id="report-title">Report a bug</h2>
      {props.alreadyReportedArea && (
        <p className="note" role="note">You already reported this area</p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (valid && !evidenceErr) props.onSubmit();
        }}
      >
        <label htmlFor="rp-file">Target file</label>
        <input id="rp-file" value={props.draft.file} onChange={(e) => props.onChange({ ...props.draft, file: e.target.value })}
               aria-invalid={!!errs.file} aria-describedby={errs.file ? "rp-file-err" : undefined} />
        {errs.file && <p className="field-err" id="rp-file-err">{errs.file}</p>}

        <label htmlFor="rp-lines">Line range</label>
        <input id="rp-lines" placeholder="e.g. src/auth/session.py:41-47" value={props.draft.lines}
               onChange={(e) => props.onChange({ ...props.draft, lines: e.target.value })}
               aria-invalid={!!errs.lines} aria-describedby={errs.lines ? "rp-lines-err" : undefined} />
        {errs.lines && <p className="field-err" id="rp-lines-err">{errs.lines}</p>}

        <label htmlFor="rp-cat">Category</label>
        <select id="rp-cat" value={props.draft.category} onChange={(e) => props.onChange({ ...props.draft, category: e.target.value })}>
          <option value="">Select…</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
        </select>

        <label htmlFor="rp-title">Title</label>
        <input id="rp-title" value={props.draft.title} onChange={(e) => props.onChange({ ...props.draft, title: e.target.value })} />
        {errs.title && <p className="field-err">{errs.title}</p>}

        <label htmlFor="rp-desc">Description</label>
        <textarea id="rp-desc" rows={5} value={props.draft.description}
                  onPaste={() => props.onChange({ ...props.draft })}
                  onChange={(e) => props.onChange({ ...props.draft, description: e.target.value })}
                  aria-describedby={errs.description ? "rp-desc-err" : "rp-desc-hint"} />
        {errs.description && <p className="field-err" id="rp-desc-err">{errs.description}</p>}
        {!errs.description && <p className="hint" id="rp-desc-hint">Explain the defect and why it is wrong (40–2000 chars)</p>}
        {props.pasteEvents > 0 && <p className="hint advisory">Paste events recorded: {props.pasteEvents} (advisory only)</p>}

        {props.requireEvidence && (
          <>
            <label htmlFor="rp-evidence">Reproduction / evidence</label>
            <textarea id="rp-evidence" rows={3} value={props.draft.evidence}
                      onChange={(e) => props.onChange({ ...props.draft, evidence: e.target.value })} />
            {evidenceErr && <p className="field-err">{evidenceErr}</p>}
          </>
        )}

        <label htmlFor="rp-impact">Impact (optional)</label>
        <input id="rp-impact" value={props.draft.impact} onChange={(e) => props.onChange({ ...props.draft, impact: e.target.value })} />

        <label htmlFor="rp-fix">Suggested fix (optional)</label>
        <input id="rp-fix" value={props.draft.suggestedFix} onChange={(e) => props.onChange({ ...props.draft, suggestedFix: e.target.value })} />

        <button type="submit" className="primary" disabled={!valid || !!evidenceErr}>
          Submit report
        </button>
        <span className="hint">Reports left for this file: {props.reportsLeft}</span>
      </form>
    </section>
  );
}
