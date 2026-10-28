import { useEffect, useState } from "react";
import { clearToken, getToken } from "./api.js";
import "./coding.css";
import "./coding-mobile.css";

const LANG = { python: "Python", c: "C", cpp: "C++", java: "Java" };
const fmt = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const tone = (s) => (s >= 65 ? "var(--good)" : s >= 50 ? "var(--warn)" : "var(--bad)");

async function api(path, method = "GET") {
  const res = await fetch(path, { method, headers: { Authorization: `Bearer ${getToken()}` } });
  if (res.status === 401) { clearToken(); window.location.replace("/"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data;
}

function Trend({ points }) {
  const w = 600, h = 120, pad = 12;
  const x = (i) => pad + (points.length === 1 ? (w - 2 * pad) / 2 : (i * (w - 2 * pad)) / (points.length - 1));
  const y = (v) => pad + (1 - v / 100) * (h - 2 * pad);
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Scores: ${points.map((p) => p.score).join(", ")}`}>
      {points.length > 1 && <polyline className="trend-line" points={points.map((p, i) => `${x(i)},${y(p.score)}`).join(" ")} />}
      {points.map((p, i) => (
        <circle key={p.id} cx={x(i)} cy={y(p.score)} r="5" fill={tone(p.score)}><title>{`${p.title}: ${p.score}`}</title></circle>
      ))}
    </svg>
  );
}

function Bars({ rows }) {
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.name}>
          <span title={r.name}>{r.name}</span>
          <div className="track"><div style={{ width: `${r.average}%` }} /></div>
          <b>{Math.round(r.average)}</b>
        </li>
      ))}
    </ul>
  );
}

function Attempt({ a, onDelete }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const load = (open) => {
    if (open && !detail) api(`/api/coding/attempts/${a.id}`).then(setDetail).catch((e) => setError(e.message));
  };
  const r = detail?.review || {};
  return (
    <details className="rv" onToggle={(e) => load(e.currentTarget.open)}>
      <summary>
        <span className="rv-score" style={{ color: tone(a.score) }}>{a.score}</span>
        <span className="rv-q">
          {a.title}
          <small className="hist-meta">{LANG[a.language] || a.language}, {a.topic || "mixed topics"}, {a.passed} of {a.total} tests, {fmt(a.created_at)}</small>
        </span>
      </summary>
      <div className="rv-body">
        {error && <p className="error" role="alert">{error}</p>}
        {!detail && !error && <p>Loading…</p>}
        {detail && (
          <>
            <h4>Your code</h4>
            <pre>{detail.code}</pre>
            {r.complexity && <><h4>Complexity</h4><p>{r.complexity}</p></>}
            {r.strengths?.length > 0 && <><h4>Strengths</h4><ul>{r.strengths.map((s) => <li key={s}>{s}</li>)}</ul></>}
            {r.issues?.length > 0 && <><h4>To improve</h4><ul>{r.issues.map((s) => <li key={s}>{s}</li>)}</ul></>}
            {r.next_step && <><h4>Next step</h4><p>{r.next_step}</p></>}
            {r.follow_up_question && <><h4>Follow-up question</h4><p>{r.follow_up_question}</p></>}
          </>
        )}
        <button className="link" onClick={() => onDelete(a.id)}>Delete this attempt</button>
      </div>
    </details>
  );
}

export default function CodingHistory() {
  const [attempts, setAttempts] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  const load = () => Promise.all([api("/api/coding/attempts"), api("/api/coding/attempts/stats")])
    .then(([list, s]) => { setAttempts(list); setStats(s); })
    .catch((e) => setError(e.message));

  useEffect(() => {
    document.documentElement.dataset.theme = localStorage.getItem("rehearse_theme") || "dark";
    if (!getToken()) { window.location.replace("/"); return; }
    load();
  }, []);

  const remove = async (id) => {
    if (!window.confirm("Delete this attempt from your history?")) return;
    await api(`/api/coding/attempts/${id}`, "DELETE").catch(() => {});
    load();
  };

  const cards = stats && [
    ["Attempts", stats.total], ["Average score", Math.round(stats.average ?? 0)],
    ["Best score", stats.best], ["All tests passed", `${stats.solve_rate}%`],
  ];

  return (
    <div className="coding-page">
      <header className="coding-bar">
        <a className="link" href="/coding">← Coding round</a>
        <b>Coding history</b>
        <a className="link" href="/">Rehearse</a>
      </header>
      <main className="coding-wrap">
        {error && <p className="error" role="alert">{error}</p>}
        {!error && attempts === null && <p className="lead">Loading your history…</p>}
        {attempts?.length === 0 && (
          <>
            <h1 className="welcome">No attempts yet</h1>
            <p className="lead">Submit a coding problem for review and it will be saved here with your code and feedback.</p>
            <a className="primary" href="/coding" style={{ display: "inline-block", textDecoration: "none" }}>Start a coding round</a>
          </>
        )}
        {attempts?.length > 0 && stats && (
          <>
            <h1 className="welcome">Your coding progress</h1>
            <div className="stat-grid">
              {cards.map(([label, value]) => <div className="stat" key={label}><b>{value}</b><span>{label}</span></div>)}
            </div>
            <h3>Score over time</h3>
            <Trend points={stats.trend} />
            <section className="hist-grid">
              <div><h3>Topics to work on</h3><Bars rows={stats.topics.slice(0, 4)} /></div>
              <div><h3>By language</h3><Bars rows={stats.languages.map((l) => ({ ...l, name: LANG[l.name] || l.name }))} /></div>
            </section>
            <h3>Past attempts</h3>
            <section className="review">{attempts.map((a) => <Attempt key={a.id} a={a} onDelete={remove} />)}</section>
          </>
        )}
      </main>
    </div>
  );
}