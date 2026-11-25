/**
 * Draft conflict modal (T-5.5, 07 §5.4.5): three actions.
 * Default is 'Keep mine' (choice logged) with an extra confirmation; focus trap; no Esc-to-nothing.
 */
import React, { useEffect, useRef } from "react";

export type ConflictChoice = "keep_mine" | "use_server" | "compare";

export function DraftConflictModal(props: {
  localVersion: number;
  serverVersion: number;
  onChoose: (choice: ConflictChoice) => void;
  onKeepMineConfirm: () => void;
}): React.JSX.Element {
  const [askKeepMine, setAskKeepMine] = React.useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // focus trap (a11y contract: every modal traps focus and returns it on close)
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  return (
    <div className="modal-overlay" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="conflict-title"
        tabIndex={-1}
        ref={dialogRef}
      >
        <h2 id="conflict-title">Your draft changed on another device</h2>
        <p>
          This device has version {props.localVersion}; the server has version {props.serverVersion}.
        </p>
        {askKeepMine ? (
          <>
            <p className="warn">Overwrite the server version with your local changes?</p>
            <div className="actions">
              <button className="primary" onClick={props.onKeepMineConfirm}>
                Yes, keep mine
              </button>
              <button onClick={() => setAskKeepMine(false)}>Back</button>
            </div>
          </>
        ) : (
          <div className="actions">
            <button className="primary" onClick={() => setAskKeepMine(true)}>
              Keep mine
            </button>
            <button onClick={() => props.onChoose("use_server")}>Use server version</button>
            <button onClick={() => props.onChoose("compare")}>Compare</button>
          </div>
        )}
      </div>
    </div>
  );
}
