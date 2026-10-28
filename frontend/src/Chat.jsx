import { useEffect, useRef, useState } from "react";
import Ladder from "./Ladder.jsx";
import { useVoice, voiceSupport } from "./voice.js";

const LEVELS = ["", "Fundamentals", "Applied", "Trade-offs", "Design and edge cases", "Expert"];

const MicIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
);

function Question({ m }) {
  return (
    <div className="msg bot">
      <div className="mark" aria-hidden>R</div>
      <div className="body">
        <p className="tags">
          <span className="tag">{m.followUp ? "Follow-up" : m.topic}</span>
          <span className="tag">Level {m.difficulty}</span>
          {m.anchor && <span className="tag resume-tag">From your resume: {m.anchor}</span>}
        </p>
        <p className="qtext">{m.text}</p>
      </div>
    </div>
  );
}

function Feedback({ m }) {
  return (
    <div className="feedback-note">
      <b>Scored {m.score} out of 10.</b> {m.text}
      {m.model && <details><summary>See a model answer</summary><p>{m.model}</p></details>}
    </div>
  );
}

export default function Chat({ view, transcript, pending, busy, error, onAnswer, onEnd }) {
  const q = view.question;
  const [text, setText] = useState("");
  const [readAloud, setReadAloud] = useState(false);
  const [handsFree, setHandsFree] = useState(false);
  const endRef = useRef(null);
  const boxRef = useRef(null);
  const hf = useRef(false);
  const ctl = useRef({});
  hf.current = handsFree;

  // In hands-free mode a pause in speech sends the answer automatically.
  const voice = useVoice({
    onText: setText,
    onSilence: (t) => { if (hf.current) { ctl.current.stop(); ctl.current.send(t); } },
  });

  const send = async (answer = text) => {
    const v = answer.trim();
    if (!v || busy) return;
    voice.stop();
    voice.cancel();
    setText("");
    const ok = await onAnswer(v);
    if (!ok) setText(v);   // keep what you said or typed if the request failed
  };
  ctl.current = { stop: voice.stop, send };

  const toggleMic = () => {
    if (voice.listening) voice.stop();
    else { voice.cancel(); voice.start(text); }
  };

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [transcript.length, busy]);
  useEffect(() => { if (!busy && !voice.listening) boxRef.current?.focus(); }, [busy, q.text]);
  useEffect(() => {
    const el = boxRef.current;
    if (el) { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 240)}px`; }
  }, [text]);
  useEffect(() => { if (voice.error) setHandsFree(false); }, [voice.error]);   // a mic problem turns hands-free off

  // Read each new question aloud; in hands-free mode, start listening when it finishes.
  useEffect(() => {
    if (!readAloud && !handsFree) return undefined;
    voice.speak(q.text, () => { if (hf.current) voice.start(""); });
    return () => voice.cancel();
  }, [q.text, readAloud, handsFree]);

  return (
    <div className="chat">
      <div className="chat-main">
        <header className="chat-head">
          <div>
            <b>{q.is_follow_up ? "Follow-up question" : `Question ${q.index} of ${q.total}`}</b>
            <span>{q.topic}</span>
          </div>
          <div className="head-right">
            <button className={`toggle ${readAloud ? "on" : ""}`} aria-pressed={readAloud}
              disabled={!voiceSupport.speak} onClick={() => setReadAloud((v) => !v)}>Read aloud</button>
            <button className={`toggle ${handsFree ? "on" : ""}`} aria-pressed={handsFree}
              disabled={!voiceSupport.speak || !voiceSupport.listen}
              title="The interviewer speaks, listens, and sends your answer when you pause"
              onClick={() => setHandsFree((v) => !v)}>Hands-free</button>
            <button className="link" disabled={busy} onClick={onEnd}>Finish</button>
          </div>
        </header>

        <div className="thread" role="log" aria-live="polite">
          {transcript.map((m, i) =>
            m.kind === "q" ? <Question key={i} m={m} /> :
            m.kind === "a" ? <div key={i} className="msg you"><p>{m.text}</p></div> :
            <Feedback key={i} m={m} />
          )}
          {pending && <div className="msg you"><p>{pending}</p></div>}
          {busy && (
            <div className="msg bot">
              <div className="mark" aria-hidden>R</div>
              <div className="typing" aria-label="Interviewer is thinking"><i /><i /><i />
                <span style={{ marginLeft: 10, color: "var(--muted)", fontSize: 15 }}>Checking your answer and preparing the next question…</span>
              </div>
            </div>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <div ref={endRef} />
        </div>

        <div className="composer-wrap">
          {voice.error && <p className="error" role="alert">{voice.error}</p>}
          {voice.speaking && (
            <p className="voice-status"><span className="wave"><i /><i /><i /><i /></span>Interviewer is speaking
              <button className="link" onClick={voice.cancel}>Stop</button></p>
          )}
          {voice.listening && (
            <p className="voice-status"><span className="wave"><i /><i /><i /><i /></span>
              {handsFree ? "Listening. I’ll send your answer when you pause." : "Listening… your words appear below."}</p>
          )}
          <div className="composer">
            <textarea ref={boxRef} rows={1} value={text} disabled={busy} aria-label="Your answer"
              placeholder="Type your answer, or press the mic and speak."
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            {voiceSupport.listen && (
              <button className={`mic ${voice.listening ? "on" : ""}`} disabled={busy} onClick={toggleMic}
                aria-pressed={voice.listening} aria-label={voice.listening ? "Stop dictation" : "Answer by voice"}><MicIcon /></button>
            )}
            <button className="send" disabled={busy || !text.trim()} aria-label="Send answer" onClick={() => send()}>↑</button>
          </div>
          <div className="composer-foot">
            <button className="link" disabled={busy} onClick={() => send("I don't know.")}>I don’t know this one</button>
            <span>{voiceSupport.listen ? "Enter sends, Shift+Enter adds a new line" : "Voice input needs Chrome or Edge"}</span>
          </div>
        </div>
      </div>

      <aside className="panel">
        <h3>Difficulty</h3>
        <Ladder history={view.history} current={q.difficulty} />
        <p className="level"><b>Level {q.difficulty}</b> {LEVELS[q.difficulty]}</p>
        <p className="legend">
          <i style={{ background: "var(--good)" }} /> strong <i style={{ background: "var(--warn)" }} /> partial <i style={{ background: "var(--bad)" }} /> weak
        </p>
      </aside>
    </div>
  );
}