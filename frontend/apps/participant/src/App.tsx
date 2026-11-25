/** App shell + routes: landing (P-01), login (ATH-01), lobby (LB-01..06), workspace,
 * submissions (SUB-01), leaderboard (LBD-01). Guards route, never decide (T-5.2). */
import React from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Workspace } from "./pages/Workspace";
import { useCountdown } from "./components/Countdown";
import { t } from "./lib/copy";

export function App(props: { signedIn?: boolean }): React.JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/rules" element={<SimplePage title="Rules" body="Versioned rules document (PUB-02). Downloadable PDF at publish time." />} />
        <Route path="/login" element={<Login />} />
        <Route path="/lobby" element={props.signedIn === false ? <Navigate to="/login" replace /> : <Lobby />} />
        <Route path="/workspace/:stageKey" element={props.signedIn === false ? <Navigate to="/login" replace /> : <WorkspaceRoute />} />
        <Route path="/submissions" element={props.signedIn === false ? <Navigate to="/login" replace /> : <Submissions />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

function Landing(): React.JSX.Element {
  const { label } = useCountdown("2026-12-05T09:30:00Z");
  return (
    <main className="page landing">
      <h1>{t("app.name")}</h1>
      <p className="tagline">{t("app.tagline")}</p>
      <p>Next round starts in <span role="timer">{label}</span></p>
      <nav>
        <Link to="/rules">Rules</Link>
        <Link to="/login">Sign in</Link>
      </nav>
    </main>
  );
}

function Login(): React.JSX.Element {
  const [failed, setFailed] = React.useState(0);
  return (
    <main className="page login">
      <h1>{t("auth.sign_in")}</h1>
      <form onSubmit={(e) => { e.preventDefault(); setFailed((n) => n + 1); }}>
        <label htmlFor="login-id">{t("auth.identifier")}</label>
        <input id="login-id" autoComplete="username" />
        <label htmlFor="login-pw">{t("auth.password")}</label>
        <input id="login-pw" type="password" autoComplete="current-password" />
        <button type="submit" className="primary">{t("auth.sign_in")}</button>
        {failed > 0 && <p className="field-err" role="alert">{t("auth.invalid_credentials")}</p>}
      </form>
    </main>
  );
}

function Lobby(): React.JSX.Element {
  const { label } = useCountdown("2026-12-05T09:30:00Z");
  return (
    <main className="page lobby">
      <h1>{t("lobby.countdown")}</h1>
      <p><span role="timer">{label}</span></p>
      <ul className="system-check" aria-label={t("lobby.system_check")}>
        <li>✓ Supported browser</li>
        <li>✓ API connectivity</li>
        <li>✓ IndexedDB available</li>
      </ul>
      <Link className="button primary" to="/workspace/level_1_explain">{t("lobby.enter_workspace")}</Link>
    </main>
  );
}

function WorkspaceRoute(): React.JSX.Element {
  const query = useQuery();
  const stageKey = query.get("stage") ?? "level_2_flags";
  return (
    <Workspace
      stage={{
        stage_key: stageKey,
        name: "Level 2 — Flag the bugs",
        deadline: "2026-12-05T10:30:00Z",
        paused: false,
        requireEvidence: stageKey.includes("2"),
        reportsLeft: 12,
      }}
      onNavigate={() => undefined}
    />
  );
}

function Submissions(): React.JSX.Element {
  const rows = [
    { id: "K7QD-92MX", title: "Non-constant-time compare", file: "src/auth/session.py", status: "Received" },
  ];
  return (
    <main className="page submissions">
      <h1>{t("ws.submissions.title")}</h1>
      <table>
        <thead><tr><th>Receipt</th><th>Title</th><th>File</th><th>Status</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}><td>{r.id}</td><td>{r.title}</td><td>{r.file}</td><td>{r.status}</td></tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

function Leaderboard(): React.JSX.Element {
  return (
    <main className="page leaderboard">
      <h1>{t("leaderboard.title")}</h1>
      <p className="banner info">{t("leaderboard.frozen")}</p>
    </main>
  );
}

function SimplePage(props: { title: string; body: string }): React.JSX.Element {
  return (
    <main className="page">
      <h1>{props.title}</h1>
      <p>{props.body}</p>
    </main>
  );
}

function NotFound(): React.JSX.Element {
  return (
    <main className="page">
      <h1>{t("common.error")}</h1>
      <Link to="/">{t("common.back")}</Link>
    </main>
  );
}
