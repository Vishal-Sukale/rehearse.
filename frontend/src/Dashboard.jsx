import { useEffect, useState } from "react";
import { getToken } from "./api.js";

const LANG = { python: "Python", c: "C", cpp: "C++", java: "Java" };
const fmtDate = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const tone = (score) => (score >= 65 ? "var(--good)" : score >= 50 ? "var(--warn)" : "var(--bad)");
const sectionTitle = { fontSize: 24, margin: "44px 0 14px" };

function TrendChart({ points }) {
  const w = 640, h = 220, pl = 34, pr = 16, pt = 14, pb = 30;
  const n = points.length;
  const x = (i) => pl + (n === 1 ? (w - pl - pr) / 2 : (i * (w - pl - pr)) / (n - 1));
  const y = (v) => pt + (1 - v / 100) * (h - pt - pb);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.score)}`).join(" ");
  return (
    <svg className="trend" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Score trend: ${points.map((p) => p.score).join(", ")}`}>
      {[0, 50, 100].map((v) => (
        <g key={v}>
          <line x1={pl} x2={w - pr} y1={y(v)} y2={y(v)} className="rung" />
          <text x={2} y={y(v) + 4} className="rung-label">{v}</text>
        </g>
      ))}
      {n > 1 && <path d={path} className="trend-line" />}
      {points.map((p, i) => (
        <circle key={p.id} cx={x(i)} cy={y(p.score)} r="5.5" fill={tone(p.score)}>
          <title>{`${fmtDate(p.date)}: ${p.score} out of 100 (${p.role || p.title})`}</title>
        </circle>
      ))}
      <text x={pl} y={h - 6} className="rung-label">{fmtDate(points[0].date)}</text>
      {n > 1 && <text x={w - pr} y={h - 6} textAnchor="end" className="rung-label">{fmtDate(points[n - 1].date)}</text>}
    </svg>
  );
}

function Bars({ rows, max = 10 }) {
  return (
    <ul className="bars">
      {rows.map(([name, value]) => (
        <li key={name}>
          <span title={name}>{name}</span>
          <div className="track"><div style={{ width: `${(value / max) * 100}%` }} /></div>
          <b>{max === 100 ? Math.round(value) : value.toFixed(1)}</b>
        </li>
      ))}
    </ul>
  );
}

// undefined while loading, then the coding stats (or null if they couldn't be fetched)
function useCodingStats() {
  const [coding, setCoding] = useState(undefined);
  useEffect(() => {
    fetch("/api/coding/attempts/stats", { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then(setCoding)
      .catch(() => setCoding(null));
  }, []);
  return coding;
}

export default function Dashboard({ stats, error, onStart }) {
  const coding = useCodingStats();
  if (error) return <div className="page"><p className="error" role="alert">{error}</p></div>;
  if (!stats) return <div className="page"><p className="lead">Loading your progress…</p></div>;

  const hasInterviews = stats.total > 0;
  const hasCoding = Boolean(coding && coding.total > 0);
  if (!hasInterviews && coding === undefined) return <div className="page"><p className="lead">Loading your progress…</p></div>;

  if (!hasInterviews && !hasCoding) {
    return (
      <div className="page">
        <h1 className="welcome">Your progress</h1>
        <p className="lead">Finish an interview or a coding round and your scores, strongest topics and weak spots will appear here.</p>
        <div className="actions">
          <button className="primary" onClick={onStart}>Start an interview</button>
          <a className="ghost" href="/coding">Coding round</a>
        </div>
      </div>
    );
  }

  const change = stats.change_since_first;
  const interviewCards = [
    ["Interviews", stats.total], ["Average score", Math.round(stats.average ?? 0)],
    ["Best score", Math.round(stats.best ?? 0)], ["Day streak", stats.streak_days],
  ];
  const codingCards = hasCoding && [
    ["Attempts", coding.total], ["Average score", Math.round(coding.average)],
    ["Best score", coding.best], ["All tests passed", `${coding.solve_rate}%`],
  ];

  return (
    <div className="page dash">
      <h1 className="welcome">Your progress</h1>
      {hasInterviews && (
        <p className="lead">
          {change == null
            ? "Complete a second interview to see how you’re improving."
            : change >= 0
              ? `Interviews: up ${change} points since your first one.`
              : `Interviews: down ${Math.abs(change)} points since your first one. Check your weak topics below.`}
        </p>
      )}

      {hasInterviews && (
        <>
          <h2 style={sectionTitle}>Interviews</h2>
          <div className="stat-grid">
            {interviewCards.map(([label, value]) => <div className="stat" key={label}><b>{value}</b><span>{label}</span></div>)}
          </div>
          <section className="dash-block"><h3>Score over time</h3><TrendChart points={stats.trend} /></section>
          <section className="two">
            <div>
              <h3>Topics to work on</h3>
              <Bars rows={stats.topics.slice(0, 4).map((t) => [t.topic, t.score])} />
              <p className="hint">Average score per topic across all interviews, weakest first.</p>
            </div>
            <div>
              <h3>Skill balance</h3>
              <Bars rows={Object.entries(stats.dimensions).map(([k, v]) => [k.charAt(0).toUpperCase() + k.slice(1), v])} />
            </div>
          </section>
        </>
      )}

      <h2 style={sectionTitle}>Coding</h2>
      {hasCoding ? (
        <>
          <div className="stat-grid">
            {codingCards.map(([label, value]) => <div className="stat" key={label}><b>{value}</b><span>{label}</span></div>)}
          </div>
          <section className="dash-block"><h3>Score over time</h3><TrendChart points={coding.trend} /></section>
          <section className="two">
            <div><h3>Topics to work on</h3><Bars max={100} rows={coding.topics.slice(0, 4).map((t) => [t.name, t.average])} /></div>
            <div><h3>By language</h3><Bars max={100} rows={coding.languages.map((l) => [LANG[l.name] || l.name, l.average])} /></div>
          </section>
          <a className="ghost" href="/coding/history">Open coding history</a>
        </>
      ) : (
        <p className="hint">No coding attempts yet. <a href="/coding">Try a coding round</a>.</p>
      )}

      <div className="actions" style={{ marginTop: 32 }}>
        <button className="primary" onClick={onStart}>Start a new interview</button>
      </div>
    </div>
  );
}