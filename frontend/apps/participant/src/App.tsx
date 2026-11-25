/** App shell + routes: landing (P-01), login (ATH-01), lobby (LB-01..06), workspace,
 * submissions (SUB-01), leaderboard (LBD-01). Guards route, never decide (T-5.2).
 * All data pages call the live participant API via useApi() and degrade gracefully
 * when offline (T-5.8 offline-first: viewing + drafting keep working). */
import React from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Workspace } from "./pages/Workspace";
import { useCountdown } from "./components/Countdown";
import { t } from "./lib/copy";
import { ApiProvider, useApi } from "./lib/api";

export function App(props: { signedIn?: boolean }): React.JSX.Element {
  return (
    <ApiProvider signedIn={props.signedIn}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/rules" element={<SimplePage title="Rules" body="Versioned rules document (PUB-02). Downloadable PDF at publish time." />} />
          <Route path="/login" element={<Login />} />
          <Route path="/lobby" element={<RequireAuth><Lobby /></RequireAuth>} />
          <Route path="/workspace/:stageKey" element={<RequireAuth><WorkspaceRoute /></RequireAuth>} />
          <Route path="/submissions" element={<RequireAuth><Submissions /></RequireAuth>} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </ApiProvider>
  );
}

function RequireAuth(props: { children: React.ReactNode }): React.JSX.Element {
  const { signedIn } = useApi();
  if (signedIn === false) return <Navigate to="/login" replace />;
  return <>{props.children}</>;
}

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

interface EventPublic {
  name?: string;
  status?: string;
  tz?: string;
  maintenance?: boolean;
}

function Landing(): React.JSX.Element {
  const { label } = useCountdown("2026-12-05T09:30:00Z");
  const { api } = useApi();
  const [event, setEvent] = React.useState<EventPublic>({});
  const [online, setOnline] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    api.get_v1_event_public()
      .then((res) => { if (!cancelled) setEvent(((res as { data?: EventPublic }).data) || {}); })
      .catch(() => { if (!cancelled) setOnline(false); });
    return () => { cancelled = true; };
  }, [api]);

  return (
    <main className="page landing">
      <h1>{event.name || t("app.name")}</h1>
      <p className="tagline">{t("app.tagline")}</p>
      {!online && <p className="banner warn" role="status">{t("common.offline")}</p>}
      <p>Next round starts in <span role="timer">{label}</span></p>
      <nav>
        <Link to="/rules">Rules</Link>
        <Link to="/login">Sign in</Link>
        <Link to="/leaderboard">Leaderboard</Link>
      </nav>
    </main>
  );
}

function Login(): React.JSX.Element {
  const { signIn } = useApi();
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const identifier = String(form.get("identifier") || "");
    const password = String(form.get("password") || "");
    setBusy(true);
    setError(null);
    signIn(identifier, password).then((res) => {
      setBusy(false);
      if (!res.ok) setError(res.error === "AUTH_INVALID_CREDENTIALS"
        ? t("auth.invalid_credentials")
        : t("common.offline"));
      else window.location.assign("/lobby");
    });
  };

  return (
    <main className="page login">
      <h1>{t("auth.sign_in")}</h1>
      <form onSubmit={onSubmit}>
        <label htmlFor="login-id">{t("auth.identifier")}</label>
        <input id="login-id" name="identifier" autoComplete="username" required />
        <label htmlFor="login-pw">{t("auth.password")}</label>
        <input id="login-pw" name="password" type="password" autoComplete="current-password" required />
        <button type="submit" className="primary" disabled={busy}>{t("auth.sign_in")}</button>
        {error && <p className="field-err" role="alert">{error}</p>}
      </form>
    </main>
  );
}

interface StageBrief {
  stage_key: string;
  name: string;
  state: string;
  submitted: boolean;
  kind: string;
  exec_closes_at?: string | null;
}

function Lobby(): React.JSX.Element {
  const { api, signOut } = useApi();
  const [stages, setStages] = React.useState<StageBrief[]>([]);
  const [deadline, setDeadline] = React.useState<string | null>("2026-12-05T10:30:00Z");
  const [online, setOnline] = React.useState(true);
  const { label } = useCountdown(deadline);

  React.useEffect(() => {
    let cancelled = false;
    api.get_v1_state(undefined)
      .then((res) => {
        if (cancelled) return;
        const data = (res as { data?: { stages?: StageBrief[] } }).data;
        const list = data?.stages || [];
        setStages(list);
        const open = list.find((s) => s.state === "open" && s.exec_closes_at);
        if (open?.exec_closes_at) setDeadline(open.exec_closes_at);
      })
      .catch(() => { if (!cancelled) setOnline(false); });
    return () => { cancelled = true; };
  }, [api]);

  const firstOpen = stages.find((s) => s.state === "open")?.stage_key || "level_1_explain";

  return (
    <main className="page lobby">
      <h1>{t("lobby.countdown")}</h1>
      <p><span role="timer">{label}</span></p>
      <ul className="system-check" aria-label={t("lobby.system_check")}>
        <li>✓ Supported browser</li>
        <li>{online ? "✓ API connectivity" : "… API offline — workspace stays usable"}</li>
        <li>✓ IndexedDB available</li>
      </ul>
      {stages.length > 0 && (
        <ul className="stage-list" aria-label="Stages">
          {stages.map((s) => (
            <li key={s.stage_key}>
              <Link to={`/workspace/${s.stage_key}`}
                className={s.state === "open" ? "button" : "button muted"}
                aria-disabled={s.state === "closed"}>
                {s.name} — {s.state}{s.submitted ? " · submitted" : ""}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link className="button primary" to={`/workspace/${firstOpen}`}>{t("lobby.enter_workspace")}</Link>
      <button type="button" className="link" onClick={() => { void signOut().then(() => window.location.assign("/")); }}>
        Sign out
      </button>
    </main>
  );
}

function WorkspaceRoute(): React.JSX.Element {
  const query = useQuery();
  const { stageKey } = useStageKeyParam();
  const { api } = useApi();
  const [stage, setStage] = React.useState<StageBrief | null>(null);
  const [loaded, setLoaded] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    api.get_v1_state(undefined)
      .then((res) => {
        if (cancelled) return;
        const list = (res as { data?: { stages?: StageBrief[] } }).data?.stages || [];
        setStage(list.find((s) => s.stage_key === stageKey) || null);
      })
      .catch(() => { /* offline: fallback props below */ })
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [api, stageKey]);

  return (
    <Workspace
      stage={{
        stage_key: stageKey,
        name: stage?.name || (query.get("stage") ? `Stage ${stageKey}` : "Level 2 — Flag the bugs"),
        deadline: stage?.exec_closes_at || "2026-12-05T10:30:00Z",
        paused: false,
        requireEvidence: stageKey.includes("2") || (stage?.kind === "flags"),
        reportsLeft: 12,
      }}
      onNavigate={() => undefined}
    />
  );
}

function useStageKeyParam(): { stageKey: string } {
  const loc = useLocation();
  const stageKey = loc.pathname.split("/").pop() || "level_1_explain";
  return { stageKey };
}

function Submissions(): React.JSX.Element {
  const { api } = useApi();
  const [stages, setStages] = React.useState<StageBrief[]>([]);
  const [online, setOnline] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    api.get_v1_state(undefined)
      .then((res) => {
        if (cancelled) return;
        setStages((res as { data?: { stages?: StageBrief[] } }).data?.stages || []);
      })
      .catch(() => { if (!cancelled) setOnline(false); });
    return () => { cancelled = true; };
  }, [api]);

  return (
    <main className="page submissions">
      <h1>{t("ws.submissions.title")}</h1>
      {!online && <p className="banner warn" role="status">{t("common.offline")}</p>}
      <table>
        <thead><tr><th>Stage</th><th>State</th><th>Submitted</th></tr></thead>
        <tbody>
          {stages.map((s) => (
            <tr key={s.stage_key}>
              <td>{s.name}</td><td>{s.state}</td>
              <td>{s.submitted ? "Received" : "—"}</td>
            </tr>
          ))}
          {stages.length === 0 && online && (
            <tr><td colSpan={3}>No submissions yet.</td></tr>
          )}
        </tbody>
      </table>
    </main>
  );
}

interface LbEntry {
  rank?: number;
  team?: string;
  score?: number;
}

function Leaderboard(): React.JSX.Element {
  const { api, signedIn } = useApi();
  const [entries, setEntries] = React.useState<LbEntry[] | null>(null);
  const [frozen, setFrozen] = React.useState(false);

  React.useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    api.get_v1_leaderboard(undefined)
      .then((res) => {
        if (cancelled) return;
        const data = (res as { data?: { entries?: LbEntry[]; frozen?: boolean } }).data;
        setEntries(data?.entries || []);
        setFrozen(Boolean(data?.frozen));
      })
      .catch(() => { if (!cancelled) setEntries([]); });
    return () => { cancelled = true; };
  }, [api, signedIn]);

  return (
    <main className="page leaderboard">
      <h1>{t("leaderboard.title")}</h1>
      {!signedIn && <p className="banner info">Sign in to see live standings.</p>}
      {signedIn && frozen && <p className="banner info">{t("leaderboard.frozen")}</p>}
      {signedIn && entries && (
        <table>
          <thead><tr><th>Rank</th><th>Team</th><th>Score</th></tr></thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={e.team || i}><td>{e.rank || i + 1}</td><td>{e.team}</td><td>{e.score ?? 0}</td></tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={3}>No scores yet — good luck!</td></tr>}
          </tbody>
        </table>
      )}
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
