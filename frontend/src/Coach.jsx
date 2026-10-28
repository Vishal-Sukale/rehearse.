import { useState } from "react";
import { coachAnswer } from "./coachApi.js";
import "./coach.css";

export default function Coach({ interviewId, index }) {
  const [state, setState] = useState({ busy: false, data: null, error: "" });
  const [copied, setCopied] = useState(false);
  if (!interviewId) return null;   // interviews saved before this feature can't be coached

  const run = async () => {
    setState({ busy: true, data: null, error: "" });
    try {
      setState({ busy: false, data: await coachAnswer(interviewId, index), error: "" });
    } catch (e) {
      setState({ busy: false, data: null, error: e.message });
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(state.data.improved_answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: nothing to do */ }
  };

  return (
    <div className="coach">
      {!state.data && (
        <button className="ghost" disabled={state.busy} onClick={run}>
          {state.busy ? "Coaching…" : "Coach me on this answer"}
        </button>
      )}
      {state.error && <p className="error" role="alert">{state.error}</p>}
      {state.data && (
        <div className="coach-card">
          <h4>A stronger version</h4>
          <p className="coach-answer">{state.data.improved_answer}</p>
          <button className="link" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
          <h4>What changed</h4>
          <ul>{state.data.what_changed.map((c) => <li key={c}>{c}</li>)}</ul>
          <h4>Next time</h4>
          <p>{state.data.next_time_tip}</p>
          <p className="hint">Anything in [brackets] is a detail only you know. Fill it in with your real experience.</p>
        </div>
      )}
    </div>
  );
}