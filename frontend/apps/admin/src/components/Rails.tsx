/**
 * EffectPreview (C-81): renders the participant-facing effect of a proposed admin action
 * BEFORE confirm, using participant copy from the catalog (E.4 — no impersonation; the
 * participant SPA never runs in the admin origin).
 */
import React from "react";

export interface EffectPreviewData {
  participantCopy: string[];
  scope: string;
  duration: string;
  undo: string;
  renderHint?: string;
}

export function EffectPreview(props: { data: EffectPreviewData | null; loading?: boolean }): React.JSX.Element {
  if (props.loading) return <div className="effect-preview" aria-busy="true">Previewing effect…</div>;
  if (!props.data) return <></>;
  return (
    <div className="effect-preview" data-testid="effect-preview" role="region" aria-label="Participant effect preview">
      <h4>What participants will see</h4>
      {props.data.participantCopy.length === 0 && <p className="hint">Nothing visible to participants.</p>}
      {props.data.participantCopy.map((copy, i) => (
        <div key={i} className="participant-banner-demo">{copy}</div>
      ))}
      <dl className="meta">
        <dt>Who sees it</dt><dd>{props.data.scope}</dd>
        <dt>Effect window</dt><dd>{props.data.duration}</dd>
        <dt>Undo</dt><dd>{props.data.undo}</dd>
      </dl>
    </div>
  );
}

/** ApprovalFlow (C-82): two distinct approvers; the UI blocks picking yourself. */
export function ApprovalFlow(props: {
  actorId: string;
  approvers: { id: string; name: string }[];
  onApprover: (id: string) => void;
  onSubmit: () => void;
}): React.JSX.Element {
  const [approver, setApprover] = React.useState("");
  const [reason, setReason] = React.useState("");
  const selfBlocked = approver === props.actorId;
  return (
    <section className="approval-flow" aria-labelledby="af-title">
      <h3 id="af-title">Two-approver flow</h3>
      <label htmlFor="af-approver">Second approver (must be a different user)</label>
      <select id="af-approver" value={approver} onChange={(e) => setApprover(e.target.value)}>
        <option value="">Select…</option>
        {props.approvers.map((a) => (
          <option key={a.id} value={a.id}>{a.name}</option>
        ))}
      </select>
      {selfBlocked && <p className="field-err" role="alert">The second approver must be a different user</p>}
      <label htmlFor="af-reason">Reason (min 20 characters)</label>
      <textarea id="af-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      <button
        className="primary"
        disabled={!approver || selfBlocked || reason.trim().length < 20}
        onClick={props.onSubmit}
      >
        Request approval
      </button>
    </section>
  );
}

/** TypedConfirm (R-34): the admin types the numeral — 'Type 7 to confirm'. */
export function TypedConfirm(props: { phrase?: string; onConfirm: () => void; disabled?: boolean }): React.JSX.Element {
  const [typed, setTyped] = React.useState("");
  const phrase = props.phrase ?? "7";
  const ready = typed === phrase;
  return (
    <div className="typed-confirm">
      <label htmlFor="tc-input">Type {phrase} to confirm</label>
      <input
        id="tc-input"
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        aria-describedby="tc-hint"
        autoComplete="off"
      />
      <p className="hint" id="tc-hint">Typed confirmation — irreversible actions require the exact phrase.</p>
      <button className="danger" disabled={!ready || props.disabled} onClick={props.onConfirm}>
        Confirm
      </button>
    </div>
  );
}

/** SensitiveBanner: persistent red border on GT/tests/rubric/pack views (08 §1.4 #4). */
export function SensitiveBanner(props: { frozen?: boolean }): React.JSX.Element {
  return (
    <div className="sensitive-banner" role="alert">
      Sensitive — access logged
      {props.frozen && " · Ground truth is frozen. Corrections require a rescore release."}
    </div>
  );
}
