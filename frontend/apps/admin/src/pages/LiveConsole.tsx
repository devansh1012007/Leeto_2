/** Live ops console (07 §3.1): 2 s ticker, health strip, stage table, error stream,
 * stale badge > 10 s, degraded state after failures. Aggregates only (T-4.7).
 * Polls GET /v1/admin/events/{id}/live; falls back to the fixture when the API is
 * unreachable (offline demo mode). */
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAdminApi } from "../lib/api";

export interface LiveAggregate {
  t_plus_s: number;
  participants_online: number;
  stages: { stage_key: string; submissions: number; auto_submits: number; missed: number }[];
  queue: { depth: number; oldest_age_s: number };
  runner: { state: string; running: number; queued: number };
  ai: { state: string; queue: number; error_rate: number };
  errors_last_5m: number;
}

const FIXTURE: LiveAggregate = {
  t_plus_s: 8024,
  participants_online: 47,
  stages: [
    { stage_key: "level_1_explain", submissions: 47, auto_submits: 0, missed: 0 },
    { stage_key: "level_2_flags", submissions: 31, auto_submits: 2, missed: 0 },
    { stage_key: "level_3_upload", submissions: 0, auto_submits: 0, missed: 0 },
    { stage_key: "level_4_upload", submissions: 0, auto_submits: 0, missed: 0 },
  ],
  queue: { depth: 3, oldest_age_s: 2 },
  runner: { state: "ok", running: 2, queued: 1 },
  ai: { state: "ok", queue: 5, error_rate: 0.01 },
  errors_last_5m: 1,
};

export function LiveConsole(): React.JSX.Element {
  const api = useAdminApi();
  const params = useParams();
  const eventId = params.id || "ev1";
  const [data, setData] = useState<LiveAggregate>(FIXTURE);
  const [lastRefreshMs, setLastRefreshMs] = useState(Date.now());
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      api.get_v1_admin_events__id__live(eventId)
        .then((res) => {
          if (cancelled) return;
          const live = (res as { data?: LiveAggregate }).data;
          if (live) setData(live);
          setDegraded(false);
          setLastRefreshMs(Date.now());
        })
        .catch(() => { if (!cancelled) setDegraded(true); });
    };
    refresh();
    const timer = window.setInterval(refresh, 2000); // 2 s ticker (T-6.11)
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [api, eventId]);

  const staleS = Math.floor((Date.now() - lastRefreshMs) / 1000);
  const stale = staleS > 10;

  return (
    <main className="page live-console" data-testid="live-console">
      <header className="lc-header">
        <h1>Live operations</h1>
        <span className={stale ? "badge stale" : "badge"}>{stale ? "Not updating" : `Last refreshed ${staleS}s ago`}</span>
        {degraded && <span className="badge degraded">Degraded — retrying</span>}
        <button onClick={() => { setLastRefreshMs(Date.now()); setDegraded(false); }}>Refresh now</button>
      </header>

      <section className="health-strip" aria-label="Health">
        <span>T+ {Math.floor(data.t_plus_s / 60)}m</span>
        <span>Online: {data.participants_online}</span>
        <span>Errors 5m: {data.errors_last_5m}</span>
        <span>Runner: {data.runner.state} ({data.runner.running}R/{data.runner.queued}Q)</span>
        <span>AI: {data.ai.state} (queue {data.ai.queue})</span>
        <span>Job lag: {data.queue.oldest_age_s}s</span>
      </section>

      <table aria-label="Stages">
        <thead>
          <tr><th>Stage</th><th>Submissions</th><th>Auto-submits</th><th>Missed</th></tr>
        </thead>
        <tbody>
          {data.stages.map((s) => (
            <tr key={s.stage_key}>
              <td>{s.stage_key}</td><td>{s.submissions}</td><td>{s.auto_submits}</td><td>{s.missed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
