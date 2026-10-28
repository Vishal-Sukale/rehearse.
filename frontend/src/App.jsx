import { useEffect, useState } from "react";
import {
  clearToken, continueInterview, deleteInterview, discardLive, endInterview, getInterview, getStats, getToken,
  health, listInterviews, listLive, me, sendAnswer, startInterview,
} from "./api.js";
import Account from "./Account.jsx";
import AuthPage from "./AuthPage.jsx";
import Chat from "./Chat.jsx";
import Dashboard from "./Dashboard.jsx";
import Scorecard from "./Scorecard.jsx";
import Setup from "./Setup.jsx";
import Sidebar from "./Sidebar.jsx";

const LOST_SESSION = "That interview could not be continued. Please start a new one.";

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("rehearse_theme") || "dark");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("rehearse_theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return online;
}

function Shell({ user, onLogout }) {
  const [theme, toggleTheme] = useTheme();
  const online = useOnline();
  const [mode, setMode] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [live, setLive] = useState([]);
  const [screen, setScreen] = useState("setup");   // setup | chat | report | dashboard
  const [view, setView] = useState(null);
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState("");
  const [transcript, setTranscript] = useState([]);
  const [pending, setPending] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [account, setAccount] = useState(false);

  const refresh = () => {
    listInterviews().then(setSessions).catch(() => {});
    listLive().then(setLive).catch(() => {});
  };
  useEffect(() => { health().then((h) => setMode(h.mode)).catch(() => setMode("down")); refresh(); }, []);

  const absorb = (next, answerText) => {
    setView(next);
    const items = [];
    if (answerText) items.push({ kind: "a", text: answerText });
    if (answerText && next.feedback) items.push({ kind: "fb", text: next.feedback, score: next.last_score, model: next.model_answer });
    if (next.status === "question") {
      const q = next.question;
      items.push({ kind: "q", text: q.text, topic: q.topic, difficulty: q.difficulty, followUp: q.is_follow_up, anchor: q.anchor });
      setScreen("chat");
    } else {
      setScreen("report");
      refresh();
    }
    setTranscript((t) => [...t, ...items]);
  };

  // Returns true on success so the composer knows whether to keep the typed text.
  const run = async (fn, answerText) => {
    setBusy(true); setError(""); setPending(answerText || "");
    try { absorb(await fn(), answerText); return true; }
    catch (e) {
      if (e.status === 404 && screen === "chat") {
        // The server no longer has this interview (for example, it was discarded or expired).
        setScreen("setup"); setView(null); setTranscript([]); setError(LOST_SESSION); refresh();
      } else {
        setError(e.message);
      }
      return false;
    }
    finally { setBusy(false); setPending(""); }
  };

  // Leaving a chat is safe: the interview is saved after every question and shows under "Unfinished".
  const leaveChat = () => {
    if (screen !== "chat") return true;
    if (!window.confirm("Leave this interview? You can continue it later from “Unfinished”.")) return false;
    refresh();
    return true;
  };

  const newInterview = () => {
    if (!leaveChat()) return;
    setScreen("setup"); setView(null); setTranscript([]); setError(""); setMenu(false);
  };
  const openProgress = () => {
    if (!leaveChat()) return;
    setMenu(false); setStats(null); setStatsError(""); setScreen("dashboard"); setView(null); setTranscript([]);
    getStats().then(setStats).catch((e) => setStatsError(e.message));
  };
  const openSession = async (id) => {
    if (!leaveChat()) return;
    setMenu(false); setError("");
    try { setView(await getInterview(id)); setScreen("report"); } catch (e) { setError(e.message); }
  };
  const removeSession = async (id) => {
    if (!window.confirm("Delete this interview from your history?")) return;
    await deleteInterview(id).catch(() => {});
    refresh();
    if (screen === "report" && view?.id === id) { setScreen("setup"); setView(null); }
  };

  const continueLive = async (id) => {
    if (screen === "chat" && view?.id === id) { setMenu(false); return; }
    if (!leaveChat()) return;
    setMenu(false); setBusy(true); setError("");
    try {
      const v = await continueInterview(id);
      setView(v); setTranscript(v.chat || []); setScreen("chat");
    } catch (e) {
      setScreen("setup"); setView(null); setTranscript([]); setError(e.message); refresh();
    } finally {
      setBusy(false);
    }
  };
  const removeLive = async (id) => {
    if (!window.confirm("Discard this unfinished interview?")) return;
    await discardLive(id).catch(() => {});
    refresh();
    if (screen === "chat" && view?.id === id) { setScreen("setup"); setView(null); setTranscript([]); }
  };

  return (
    <>
      {!online && <div className="offline" role="status">You’re offline. Reconnect to continue.</div>}
      <div className={`shell ${menu ? "menu-open" : ""}`}>
        <Sidebar user={user} sessions={sessions} live={live}
          activeId={screen === "report" ? view?.id : null} activeLiveId={screen === "chat" ? view?.id : null}
          screen={screen} theme={theme} onTheme={toggleTheme} onNew={newInterview} onProgress={openProgress}
          onOpen={openSession} onDelete={removeSession} onContinue={continueLive} onDiscardLive={removeLive}
          onAccount={() => { setMenu(false); setAccount(true); }} onLogout={onLogout} />
        <div className="scrim" onClick={() => setMenu(false)} />
        <section className="content">
          <button className="menu-btn" aria-label="Open menu" onClick={() => setMenu(true)}>☰</button>
          {screen === "setup" && (
            <Setup name={user.name} mode={mode} busy={busy} error={error}
              onStart={(cfg) => { setTranscript([]); run(() => startInterview(cfg)); }} />
          )}
          {screen === "chat" && view && (
            <Chat view={view} transcript={transcript} pending={pending} busy={busy} error={error}
              onAnswer={(a) => run(() => sendAnswer(view.id, a), a)} onEnd={() => run(() => endInterview(view.id))} />
          )}
          {screen === "report" && view && (
            <Scorecard card={view.scorecard} history={view.history} transcript={view.transcript || []} onRestart={newInterview} />
          )}
          {screen === "dashboard" && <Dashboard stats={stats} error={statsError} onStart={newInterview} />}
        </section>
      </div>
      {account && <Account user={user} onClose={() => setAccount(false)} onDeleted={onLogout} />}
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(Boolean(getToken()));

  useEffect(() => {
    if (getToken()) me().then(setUser).catch(clearToken).finally(() => setBooting(false));
    const expired = () => setUser(null);
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, []);

  if (booting) return <div className="boot">Loading…</div>;
  if (!user) return <AuthPage onAuth={setUser} />;
  return <Shell key={user.id} user={user} onLogout={() => { clearToken(); setUser(null); }} />;
}