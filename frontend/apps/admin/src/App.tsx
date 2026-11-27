/** Admin app shell (A-01/A-02 + 08 §1.2): top bar with environment chip + event switcher +
 * presence, left nav, incident banner on every page (C-94). No impersonation routes exist (R-28). */
import React from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AnswerAuthority } from "./pages/AnswerAuthority";
import { EmergencyRoom } from "./pages/EmergencyRoom";
import { LiveConsole } from "./pages/LiveConsole";

export interface AdminEnv { env: "dev" | "staging" | "prod"; eventName: string }

export function App(props: { env?: AdminEnv }): React.JSX.Element {
  const env = props.env ?? { env: "dev" as const, eventName: "Bug Hunt CTF 2026" };
  const [incident, setIncident] = React.useState<{ severity: string; summary: string } | null>({
    severity: "sev2",
    summary: "Elevated API latency in stage 2",
  });

  return (
    <BrowserRouter basename="/">
      {incident && (
        <div className="incident-banner" role="alert">
          Incident {incident.severity}: {incident.summary}
          <button className="ghost small" onClick={() => setIncident(null)}>Resolve</button>
        </div>
      )}
      <header className="admin-topbar">
        <span className="logo">BHCTF</span>
        <select aria-label="Event switcher" defaultValue={env.eventName}>
          <option>{env.eventName}</option>
        </select>
        <span className={env.env === "prod" ? "env-chip prod" : "env-chip"} data-testid="env-chip">
          {env.env === "prod" ? "PRODUCTION" : env.env === "staging" ? "STAGING" : "LOCAL"}
        </span>
        <span className="grow" />
        <span className="presence" aria-label="Admins online">AL</span>
      </header>
      <div className="admin-body">
        <nav className="admin-nav" aria-label="Admin sections">
          <Link to="/">Home</Link>
          <Link to="/events/ev1/live">Live</Link>
          <Link to="/events/ev1/emergency">Emergency</Link>
          <Link to="/challenges/ch1/answer-authority">Answer Authority</Link>
          <Link to="/review">Review</Link>
          <Link to="/audit">Audit</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events/:id/live" element={<LiveConsole />} />
          <Route path="/events/:id/emergency" element={<EmergencyRoom />} />
          <Route path="/challenges/:id/answer-authority" element={<AnswerAuthority />} />
          <Route path="/review" element={<Placeholder title="Review queue (A-21/A-22)" />} />
          <Route path="/audit" element={<Placeholder title="Audit viewer (A-30) — chain verify + export" />} />
          <Route path="*" element={<Placeholder title="Not found" />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

function Home(): React.JSX.Element {
  return (
    <main className="page">
      <h1>Admin home</h1>
      <p>Pending reviews: 3 · Open disputes: 1 · Errors (5m): 1</p>
    </main>
  );
}

function Placeholder(props: { title: string }): React.JSX.Element {
  return (
    <main className="page">
      <h1>{props.title}</h1>
    </main>
  );
}
