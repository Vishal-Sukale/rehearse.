import Logo from "./Logo.jsx";

const fmt = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export default function Sidebar({
  user, sessions, live, activeId, activeLiveId, screen, theme, onTheme,
  onNew, onProgress, onOpen, onDelete, onContinue, onDiscardLive, onAccount, onLogout,
}) {
  return (
    <aside className="sidebar">
      <div className="sb-head sb-head-row">
        <Logo size={30} />
        <button className="theme-btn" onClick={onTheme} aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
          title={theme === "light" ? "Dark theme" : "Light theme"}>{theme === "light" ? "☾" : "☀"}</button>
      </div>
      <button className="new" onClick={onNew}>New interview</button>
      <a className="nav-btn" href="/coding">Coding round</a>
      <a className="nav-btn" href="/coding/history">Coding history</a>
      <button className={`nav-btn ${screen === "dashboard" ? "on" : ""}`} onClick={onProgress}>Your progress</button>

      {live.length > 0 && (
        <>
          <p className="sb-title">Unfinished</p>
          <div className="live-list">
            {live.map((s) => (
              <div key={s.id} className={`session ${s.id === activeLiveId ? "on" : ""}`}>
                <button className="open" onClick={() => onContinue(s.id)}>
                  <b>{s.role}</b>
                  <span>{s.answered} of {s.total} answered, tap to continue</span>
                </button>
                <button className="del" aria-label={`Discard unfinished ${s.role} interview`} onClick={() => onDiscardLive(s.id)}>×</button>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="sb-title">Past interviews</p>
      <nav className="sessions" aria-label="Past interviews">
        {sessions.length === 0 && <p className="empty">Finished interviews are saved here.</p>}
        {sessions.map((s) => (
          <div key={s.id} className={`session ${s.id === activeId ? "on" : ""}`}>
            <button className="open" onClick={() => onOpen(s.id)}>
              <b>{s.role}</b>
              <span>{fmt(s.created_at)}, scored {Math.round(s.overall_score)} of 100</span>
            </button>
            <button className="del" aria-label={`Delete ${s.role} interview`} onClick={() => onDelete(s.id)}>×</button>
          </div>
        ))}
      </nav>
      <div className="sb-foot">
        <div className="avatar" aria-hidden>{user.name.trim()[0]?.toUpperCase()}</div>
        <div className="who"><b>{user.name}</b><span>{user.email}</span></div>
        <div className="sb-links">
          <button className="link" onClick={onAccount}>Account</button>
          <button className="link" onClick={onLogout}>Sign out</button>
        </div>
      </div>
    </aside>
  );
}