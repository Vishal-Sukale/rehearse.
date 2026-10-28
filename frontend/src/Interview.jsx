import { useState } from "react";
import Ladder from "./Ladder.jsx";

const LEVELS = ["", "Fundamentals", "Applied", "Trade-offs", "Design & edge cases", "Expert"];

export default function Interview({ view, history, busy, error, onAnswer, onEnd }) {
  const q = view.question;
  const [text, setText] = useState("");
  const send = (answer) => answer.trim() && !busy && onAnswer(answer.trim());

  return (
    <main className="interview">
      <section className="stage">
        <p className="progress">
          {q.is_follow_up ? "Follow-up question" : `Question ${q.index} of ${q.total}`}
          <span> on {q.topic}</span>
        </p>
        <h2 className="question">{q.text}</h2>

        <textarea
          autoFocus
          rows={9}
          value={text}
          disabled={busy}
          placeholder="Answer as you would out loud. Cover your approach, trade-offs and edge cases."
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") send(text); }}
        />
        {error && <p className="error" role="alert">{error}</p>}
        <div className="actions">
          <button className="primary" disabled={busy || !text.trim()} onClick={() => send(text)}>
            {busy ? "Reviewing your answer…" : "Send answer"}
          </button>
          <button className="ghost" disabled={busy} onClick={() => send("I don't know.")}>I don’t know this one</button>
          <button className="link" disabled={busy} onClick={onEnd}>Finish and see scorecard</button>
        </div>
        <p className="hint">Press Ctrl or ⌘ + Enter to send.</p>
      </section>

      <aside className="side">
        <h3>Difficulty</h3>
        <Ladder history={history} current={q.difficulty} />
        <p className="level"><b>Level {q.difficulty}</b> {LEVELS[q.difficulty]}</p>
        <p className="legend">
          <i style={{ background: "var(--good)" }} /> strong
          <i style={{ background: "var(--warn)" }} /> partial
          <i style={{ background: "var(--bad)" }} /> weak
        </p>
        {q.feedback && (
          <div className="feedback">
            <h3>On your last answer</h3>
            <p>{q.feedback}</p>
          </div>
        )}
      </aside>
    </main>
  );
}
