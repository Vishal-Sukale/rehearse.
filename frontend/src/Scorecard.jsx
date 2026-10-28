import { useMemo, useState } from "react";
import Coach from "./Coach.jsx";
import { analyzeDelivery, summarizeDelivery } from "./delivery.js";
import Ladder from "./Ladder.jsx";

const BAND = {
  strong_hire: ["Strong hire signal", "var(--good)"],
  hire: ["Hire signal", "var(--good)"],
  lean_hire: ["Borderline", "var(--warn)"],
  no_hire: ["Not ready yet", "var(--bad)"],
};
const tone = (s) => (s >= 7 ? "var(--good)" : s >= 4 ? "var(--warn)" : "var(--bad)");

function Bars({ rows }) {
  return (
    <ul className="bars">
      {rows.map(([name, value]) => (
        <li key={name}>
          <span>{name}</span>
          <div className="track"><div style={{ width: `${value * 10}%` }} /></div>
          <b>{value.toFixed(1)}</b>
        </li>
      ))}
    </ul>
  );
}

function Review({ items, expandAll }) {
  return (
    <section className="review">
      <h3>Review your answers</h3>
      {items.map((t, i) => {
        const d = analyzeDelivery(t.answer);
        return (
          <details key={i} className="rv" open={expandAll}>
            <summary>
              <span className="rv-score" style={{ color: tone(t.score) }}>{t.score}</span>
              <span className="rv-q">{t.follow_up ? "Follow-up: " : ""}{t.question}</span>
            </summary>
            <div className="rv-body">
              <p className="tags">
                <span className="tag">{t.topic}</span>
                <span className="tag">Level {t.difficulty}</span>
                {t.anchor && <span className="tag resume-tag">From your resume: {t.anchor}</span>}
              </p>
              <h4>Your answer</h4>
              <p className="rv-answer">{t.answer}</p>
              <p className="rv-delivery">{d.words} words, {d.fillers} filler words, {d.hedges} hedging phrases, {d.numbers} numbers</p>
              <h4>Feedback</h4>
              <p>{t.feedback}</p>
              <p className="rv-dims">Correctness {t.correctness}/10, depth {t.depth}/10, communication {t.communication}/10</p>
              {t.covered?.length > 0 && <><h4>What you covered</h4><ul>{t.covered.map((c) => <li key={c}>{c}</li>)}</ul></>}
              {t.missed?.length > 0 && <><h4>What you missed</h4><ul>{t.missed.map((c) => <li key={c}>{c}</li>)}</ul></>}
              {t.model_answer && <><h4>Model answer</h4><p>{t.model_answer}</p></>}
              <Coach interviewId={t.interview_id} index={i} />
            </div>
          </details>
        );
      })}
    </section>
  );
}

export default function Scorecard({ card, history, transcript = [], onRestart }) {
  const [expandAll, setExpandAll] = useState(false);
  const [copied, setCopied] = useState(false);
  // Skip blank / "I don't know" answers so they don't distort the averages.
  const delivery = useMemo(
    () => summarizeDelivery(transcript.filter((t) => t.score >= 1).map((t) => t.answer)),
    [transcript],
  );
  const [label, tone2] = BAND[card.hiring_band];
  const a = card.analysis;

  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(card, null, 2)], { type: "application/json" }));
    Object.assign(document.createElement("a"), { href: url, download: "scorecard.json" }).click();
    URL.revokeObjectURL(url);
  };
  const printPdf = () => { setExpandAll(true); setTimeout(() => window.print(), 150); };

  const share = async () => {
    const text = [
      `My Rehearse mock interview: ${Math.round(card.overall_score)}/100 (${label}) for ${card.role}.`,
      a?.strengths?.length ? `Strengths: ${a.strengths.join("; ")}` : null,
      a?.weaknesses?.length ? `Working on: ${a.weaknesses.join("; ")}` : null,
    ].filter(Boolean).join("\n");
    try {
      if (navigator.share) {
        await navigator.share({ title: "My mock interview result", text });
      } else {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch { /* sharing was cancelled */ }
  };

  if (card.questions_answered === 0) {
    return (
      <div className="page report">
        <h1 className="verdict">No answers yet</h1>
        <p className="summary">You finished before answering anything, so there’s nothing to score.</p>
        <button className="primary" onClick={onRestart}>Start a new interview</button>
      </div>
    );
  }

  return (
    <div className="page report">
      <header className="hero">
        <div>
          <div className="score" style={{ color: tone2 }}>{Math.round(card.overall_score)}</div>
          <p className="verdict">{label}</p>
          <p className="meta">
            {card.role}, {card.seniority} level. You answered {card.questions_answered} questions and
            held your ground up to difficulty {card.highest_difficulty_passed} of 5.
          </p>
        </div>
        <Ladder history={history} w={300} h={240} />
      </header>

      <section className="two">
        <div>
          <h3>How you answered</h3>
          <Bars rows={[
            ["Correctness", card.dimension_averages.correctness],
            ["Depth", card.dimension_averages.depth],
            ["Communication", card.dimension_averages.communication],
          ]} />
        </div>
        <div>
          <h3>By topic</h3>
          <Bars rows={card.topic_breakdown.map((t) => [t.topic, t.average_score])} />
        </div>
      </section>

      {a && (
        <section className="analysis">
          <p className="summary">{a.summary}</p>
          <div className="two">
            <div><h3>What went well</h3><ul>{a.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>
            <div><h3>What to work on</h3><ul>{a.weaknesses.map((s) => <li key={s}>{s}</li>)}</ul></div>
          </div>
          <h3>Study plan</h3>
          <ol>{a.study_plan.map((s) => <li key={s}>{s}</li>)}</ol>
        </section>
      )}

      {delivery && (
        <section className="delivery">
          <h3>Your delivery</h3>
          <div className="stat-grid">
            <div className="stat"><b>{delivery.avgWords}</b><span>words per answer</span></div>
            <div className="stat"><b>{delivery.fillerRate}</b><span>filler words per 100</span></div>
            <div className="stat"><b>{delivery.hedges}</b><span>hedging phrases</span></div>
            <div className="stat"><b>{delivery.numbers}</b><span>numbers mentioned</span></div>
          </div>
          {delivery.tips.length > 0 && <ul>{delivery.tips.map((t) => <li key={t}>{t}</li>)}</ul>}
        </section>
      )}

      {transcript.length > 0
        ? <Review items={transcript} expandAll={expandAll} />
        : <p className="hint">A detailed answer review wasn’t saved for this interview. New interviews include it.</p>}

      <div className="actions no-print">
        <button className="primary" onClick={onRestart}>Start a new interview</button>
        <button className="ghost" onClick={share}>{copied ? "Copied to clipboard" : "Share result"}</button>
        {transcript.length > 0 && (
          <button className="ghost" onClick={() => setExpandAll((v) => !v)}>{expandAll ? "Collapse answers" : "Expand all answers"}</button>
        )}
        <button className="ghost" onClick={printPdf}>Save as PDF</button>
        <button className="ghost" onClick={download}>Download data (JSON)</button>
      </div>
    </div>
  );
}