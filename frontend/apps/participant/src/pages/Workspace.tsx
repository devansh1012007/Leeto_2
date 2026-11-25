/**
 * Workspace (WS-01..WS-12 core): HUD, explorer, code view, report panel, submissions
 * drawer, run panel. Monaco loads lazily; copy-friction is documented non-security.
 */
import React, { useEffect, useState } from "react";
import { Countdown } from "../components/Countdown";
import { DraftConflictModal, type ConflictChoice } from "../components/DraftConflictModal";
import { ReportPanel, type ReportDraft } from "../components/ReportPanel";
import { SyncChip, deriveSyncState, type SyncState } from "../components/SyncChip";
import { t } from "../lib/copy";
import { installShortcuts } from "../lib/shortcuts";

export interface StageInfo {
  stage_key: string;
  name: string;
  deadline: string | null;
  paused: boolean;
  requireEvidence: boolean;
  reportsLeft: number;
}

const FILES = [
  { path: "src/auth/session.py", lines: 120, reported: 2 },
  { path: "src/db/users.py", lines: 88, reported: 0 },
  { path: "src/api/orders.py", lines: 240, reported: 1 },
  { path: "src/util/parse.py", lines: 64, reported: 0 },
];

const CODE = `def verify_session(token, stored):
    # line 40
    if stored == token:      # reported: non-constant-time compare
        return True
    return False
`;

export function Workspace(props: {
  stage: StageInfo;
  onNavigate: (path: string) => void;
}): React.JSX.Element {
  const [file, setFile] = useState(FILES[0].path);
  const [offline, setOffline] = useState(false);
  const [outbox, setOutbox] = useState(0);
  const [serverSavedAt, setServerSavedAt] = useState<number | null>(null);
  const [lastSubmitAccepted, setLastSubmitAccepted] = useState(false);
  const [conflict, setConflict] = useState<{ local: number; server: number } | null>(null);
  const [selection, setSelection] = useState<string>("");
  const [pasteEvents, setPasteEvents] = useState(0);
  const [draft, setDraft] = useState<ReportDraft>({
    file: FILES[0].path, lines: "", category: "", title: "", description: "", impact: "", evidence: "", suggestedFix: "",
  });
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => installShortcuts({
    onPalette: () => alert("command palette"),
    onQuickOpen: () => setHelpOpen(true),
    onSearchFiles: () => alert("search"),
    onToggleExplorer: () => alert("explorer"),
    onToggleReportPanel: () => alert("panel"),
    onNewReport: () => setSelection("40-44"),
    onSubmitReport: () => setLastSubmitAccepted(true),
    onRunScratch: () => alert("run"),
    onTab: (n) => alert(`tab ${n}`),
    onNextMarker: () => alert("next marker"),
    onPrevMarker: () => alert("prev marker"),
    onHelp: () => setHelpOpen((v) => !v),
  }), []);

  useEffect(() => {
    const stop = () => void 0;
    void stop;
    // offline watcher (debounced 3 s) — WS-08
    const timer = window.setInterval(() => setOffline(!navigator.onLine), 3000);
    return () => window.clearInterval(timer);
  }, []);

  const syncState: SyncState = deriveSyncState({
    offline, outboxSize: outbox, serverSavedAt, lastSubmitAccepted,
  });

  return (
    <div className="workspace" data-testid="workspace">
      <header className="hud">
        <span className="stage-name">{props.stage.name}</span>
        <Countdown deadline={props.stage.deadline} />
        <span aria-live="polite">Reports acknowledged: 3</span>
        <SyncChip state={syncState} />
        {offline && <span className="banner warn" role="alert">{t("offline.banner")}</span>}
      </header>

      {props.stage.paused && (
        <div className="banner critical" role="alert">{t("ws.pause_banner")}</div>
      )}

      <div className="panes">
        <nav className="explorer" aria-label="Files">
          <ul>
            {FILES.map((f) => (
              <li key={f.path}>
                <button
                  className={f.path === file ? "active" : ""}
                  onClick={() => { setFile(f.path); setDraft({ ...draft, file: f.path }); }}
                >
                  {f.path}
                  {f.reported > 0 && <span className="reported" aria-label={`${f.reported} reported`}>●{f.reported}</span>}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <section className="code-area" aria-label="Code view">
          <pre className="code" aria-label={file}>{CODE}</pre>
          <p className="hint">{selection ? `Selected lines ${selection} — press Alt+N to report` : "Click a line, drag a range, then report"}</p>
        </section>

        <ReportPanel
          draft={draft}
          onChange={(d) => { setDraft(d); setServerSavedAt(null); }}
          onSubmit={() => { setLastSubmitAccepted(true); setOutbox(0); }}
          maxSpan={25}
          reportsLeft={props.stage.reportsLeft}
          alreadyReportedArea={draft.lines.startsWith("40")}
          requireEvidence={props.stage.requireEvidence}
          pasteEvents={pasteEvents}
        />
      </div>

      {conflict && (
        <DraftConflictModal
          localVersion={conflict.local}
          serverVersion={conflict.server}
          onChoose={(c: ConflictChoice) => { void c; setConflict(null); }}
          onKeepMineConfirm={() => { setConflict(null); setServerSavedAt(Date.now()); }}
        />
      )}

      {helpOpen && (
        <div className="modal-overlay" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
            <h2>Keyboard shortcuts</h2>
            <ul>
              <li>Ctrl/Cmd+K — command palette</li>
              <li>Ctrl/Cmd+P — quick-open file</li>
              <li>Alt+N — new report from selection</li>
              <li>Ctrl/Cmd+Enter — submit report</li>
              <li>F8 / Shift+F8 — next / previous marker</li>
              <li>? — this help</li>
            </ul>
            <button onClick={() => setHelpOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
