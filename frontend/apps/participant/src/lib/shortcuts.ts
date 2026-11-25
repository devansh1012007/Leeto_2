/**
 * Keyboard contract (T-5.10, 07 §5.6): full shortcut list; `?`, `r`, `l` suppressed
 * while focus is in an editable element.
 */
export interface ShortcutHandlers {
  onPalette: () => void;
  onQuickOpen: () => void;
  onSearchFiles: () => void;
  onToggleExplorer: () => void;
  onToggleReportPanel: () => void;
  onNewReport: () => void;
  onSubmitReport: () => void;
  onRunScratch: () => void;
  onTab: (n: number) => void;
  onNextMarker: () => void;
  onPrevMarker: () => void;
  onHelp: () => void;
}

function inEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return (
    el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable
  );
}

export function installShortcuts(handlers: ShortcutHandlers): () => void {
  const onKey = (e: KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); handlers.onPalette(); return; }
    if (mod && e.key.toLowerCase() === "p") { e.preventDefault(); handlers.onQuickOpen(); return; }
    if (mod && e.shiftKey && e.key.toLowerCase() === "f") { e.preventDefault(); handlers.onSearchFiles(); return; }
    if (mod && e.key.toLowerCase() === "b") { e.preventDefault(); handlers.onToggleExplorer(); return; }
    if (mod && e.key.toLowerCase() === "j") { e.preventDefault(); handlers.onToggleReportPanel(); return; }
    if (e.altKey && e.key.toLowerCase() === "n") { e.preventDefault(); handlers.onNewReport(); return; }
    if (mod && e.key === "Enter") { e.preventDefault(); handlers.onSubmitReport(); return; }
    if (mod && e.shiftKey && e.key === "Enter") { e.preventDefault(); handlers.onRunScratch(); return; }
    if (e.altKey && /^[1-9]$/.test(e.key)) { e.preventDefault(); handlers.onTab(Number(e.key)); return; }
    if (e.key === "F8") { e.preventDefault(); if (e.shiftKey) handlers.onPrevMarker(); else handlers.onNextMarker(); return; }
    // bare-letter shortcuts suppressed in editable elements (T-5.10)
    if (!inEditable(e.target)) {
      if (e.key === "?") { e.preventDefault(); handlers.onHelp(); }
      if (e.key === "r") { e.preventDefault(); handlers.onNewReport(); }
      if (e.key === "l") { e.preventDefault(); handlers.onQuickOpen(); }
    }
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}
