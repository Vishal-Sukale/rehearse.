import { useEffect, useRef, useState } from "react";
import { clearToken, getToken } from "./api.js";
import "./coding.css";
import "./coding-mobile.css";

const TOPICS = ["Strings", "Arrays", "Hashing", "Sorting & searching", "Two pointers", "Stacks & queues", "Recursion", "Dynamic programming", "Math", "Bit manipulation"];
const LEVELS = [["Easy", 2], ["Medium", 3], ["Hard", 4]];
const BAND = {
  strong_hire: ["Strong hire signal", "var(--good)"],
  hire: ["Hire signal", "var(--good)"],
  lean_hire: ["Borderline", "var(--warn)"],
  no_hire: ["Not ready yet", "var(--bad)"],
};
const RUN_LIMIT_MS = 15000;

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) { clearToken(); window.location.replace("/"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data;
}

const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const norm = (s) => String(s ?? "").split("\n").map((l) => l.replace(/\s+$/, "")).join("\n").replace(/\s+$/, "");
const clip = (s, n = 80) => (s.length > n ? `${s.slice(0, n)}…` : s);

export default function CodingPage() {
  const [phase, setPhase] = useState("setup");   // setup | solve | done
  const [topic, setTopic] = useState(TOPICS[0]);
  const [level, setLevel] = useState(3);
  const [languages, setLanguages] = useState([{ id: "python", label: "Python", available: true }]);
  const [language, setLanguage] = useState("python");
  const [problem, setProblem] = useState(null);
  const [codes, setCodes] = useState({});          // each language keeps its own code
  const [tests, setTests] = useState(null);        // null while preparing, then [{ input, expected }]
  const [engine, setEngine] = useState("loading"); // loading | ready | error
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [review, setReview] = useState(null);
  const [saved, setSaved] = useState("");          // "" | "saved" | "failed"
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [hints, setHints] = useState(0);
  const worker = useRef(null);
  const pending = useRef(null);
  const counter = useRef(0);
  const escaped = useRef(false);

  const code = problem ? (codes[language] ?? problem.starters[language]) : "";
  const setCode = (value) => setCodes((c) => ({ ...c, [language]: value }));

  const startEngine = () => {
    worker.current?.terminate();
    setEngine("loading");
    const w = new Worker("/pyrunner.js");
    w.onmessage = (e) => {
      const m = e.data;
      if (m.type === "ready") setEngine("ready");
      else if (m.type === "error") setEngine("error");
      else if (pending.current && m.id === pending.current.id) {
        clearTimeout(pending.current.timer);
        pending.current.resolve(m);
        pending.current = null;
      }
    };
    w.onerror = () => setEngine("error");
    worker.current = w;
  };

  // Send a job to the Python worker. An endless loop can't be interrupted politely, so we restart the engine.
  const ask = (payload) => new Promise((resolve) => {
    const id = ++counter.current;
    const timer = setTimeout(() => {
      pending.current = null;
      startEngine();
      resolve({ fatal: "Time limit exceeded (15 seconds). Check for an endless loop." });
    }, RUN_LIMIT_MS);
    pending.current = { id, resolve, timer };
    worker.current.postMessage({ id, ...payload });
  });

  useEffect(() => {
    document.documentElement.dataset.theme = localStorage.getItem("rehearse_theme") || "dark";
    if (!getToken()) { window.location.replace("/"); return undefined; }
    startEngine();
    api("/api/coding/languages").then(setLanguages).catch(() => {});
    return () => worker.current?.terminate();
  }, []);

  useEffect(() => {
    if (phase !== "solve") return undefined;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  // Prepare the tests once per problem: run the AI's reference solution to get the expected output for each input.
  useEffect(() => {
    if (!problem || engine !== "ready" || tests !== null) return undefined;
    let cancelled = false;
    ask({ code: problem.reference_solution, inputs: problem.test_inputs }).then((out) => {
      if (cancelled) return;
      const good = (out.results || [])
        .map((r, i) => ({ input: problem.test_inputs[i], expected: norm(r.stdout), ok: r.ok }))
        .filter((t) => t.ok && t.expected !== "")
        .map(({ input, expected }) => ({ input, expected }));
      if (good.length === 0) setError("We couldn't prepare tests for this problem. Please try another one.");
      setTests(good);
    });
    return () => { cancelled = true; };
  }, [problem, engine, tests]);

  const runTests = async () => {
    const inputs = tests.map((t) => t.input);
    let raw;
    if (language === "python") {
      const r = await ask({ code, inputs });
      if (r.fatal) return { fatal: r.fatal };
      raw = r.results.map((o) => ({ ok: o.ok, stdout: o.stdout, error: o.error || "" }));
    } else {
      try {
        const r = await api("/api/coding/run", { language, code, inputs });
        if (r.compile_error) return { fatal: `Compile error:\n${r.compile_error}` };
        raw = r.results.map((o) => ({
          ok: !o.timed_out && o.exit_code === 0,
          stdout: o.stdout,
          error: o.timed_out ? "Time limit exceeded" : o.exit_code !== 0 ? clip(o.stderr || `Exit code ${o.exit_code}`, 200) : "",
        }));
      } catch (e) {
        return { fatal: e.message };
      }
    }
    return {
      results: tests.map((t, i) => {
        const got = norm(raw[i]?.stdout);
        return { input: t.input, expected: t.expected, got, error: raw[i]?.error || "", ok: Boolean(raw[i]?.ok) && got === t.expected };
      }),
    };
  };

  const run = async () => {
    setRunning(true); setError(""); setResults(null);
    const out = await runTests();
    setResults(out); setRunning(false);
    return out;
  };

  const begin = async () => {
    setBusy(true); setError("");
    try {
      const p = await api("/api/coding/problem", { topic: topic.trim(), difficulty: level });
      setProblem(p); setCodes({}); setTests(null); setResults(null); setReview(null); setSaved(""); setSeconds(0); setHints(0);
      setPhase("solve");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    const out = await run();
    if (!out.results) return;   // a compile error, syntax error or timeout: fix it and submit again
    const passed = out.results.filter((r) => r.ok).length;
    const total = out.results.length;
    const failures = out.results.filter((r) => !r.ok).slice(0, 5)
      .map((r) => `input ${clip(r.input.trim().replace(/\n/g, " / "), 60)} expected ${clip(r.expected, 60)}, got ${clip(r.error || r.got, 60)}`);
    setBusy(true);
    try {
      const r = await api("/api/coding/review", {
        language, title: problem.title, statement: problem.statement, code, passed, total, failures,
        expected_complexity: problem.expected_complexity, reference_solution: problem.reference_solution, seconds,
      });
      setReview(r); setPhase("done"); setSaved("");
      api("/api/coding/attempts", {   // save it to the history (the server recomputes the score itself)
        topic: topic.trim(), difficulty: level, language, title: problem.title, code, passed, total, quality: r.quality, seconds,
        review: {
          complexity: r.complexity, meets_expected_complexity: r.meets_expected_complexity, strengths: r.strengths,
          issues: r.issues, next_step: r.next_step, follow_up_question: r.follow_up_question,
        },
      }).then(() => setSaved("saved")).catch(() => setSaved("failed"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Escape") { escaped.current = true; return; }
    if (e.key !== "Tab") { escaped.current = false; return; }
    if (escaped.current) { escaped.current = false; return; }   // Esc, then Tab, leaves the editor (keyboard access)
    e.preventDefault();
    const el = e.target;
    const at = el.selectionStart;
    setCode(code.slice(0, at) + "    " + code.slice(el.selectionEnd));
    requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = at + 4; });
  };

  const passed = results?.results?.filter((r) => r.ok).length ?? 0;
  const status = engine === "ready" ? "Test engine ready" : engine === "error" ? "Test engine failed to load. Check your connection." : "Loading test engine…";
  const canRun = engine === "ready" && tests !== null && tests.length > 0 && !running && !busy;
  const label = languages.find((l) => l.id === language)?.label || language;

  const LanguagePicker = ({ onPick }) => (
    <div className="segmented" role="radiogroup" aria-label="Language">
      {languages.map((l) => (
        <button type="button" key={l.id} role="radio" aria-checked={language === l.id} disabled={!l.available}
          title={l.available ? "" : "Needs a code runner"} className={language === l.id ? "on" : ""}
          onClick={() => onPick(l.id)}>{l.label}</button>
      ))}
    </div>
  );

  return (
    <div className="coding-page">
      <header className="coding-bar">
        <a className="link" href="/">← Rehearse</a>
        <b>Coding round</b>
        <a className="link" href="/coding/history">History</a>
        <span className="engine">{status}</span>
      </header>

      {phase === "setup" && (
        <main className="coding-wrap">
          <h1 className="welcome">Coding round</h1>
          <p className="lead">Solve a problem the way you would in a real interview. You write a program that reads input and prints the answer.</p>
          <div className="form">
            <div className="field">
              <span>Topic</span>
              <div className="chips">
                {TOPICS.map((t) => (
                  <button type="button" key={t} aria-pressed={topic === t} className={topic === t ? "chip on" : "chip"} onClick={() => setTopic(t)}>{t}</button>
                ))}
              </div>
              <input value={topic} maxLength={80} onChange={(e) => setTopic(e.target.value)} placeholder="Or type your own topic, like binary search on the answer" />
            </div>
            <div className="field">
              <span id="lv">Difficulty</span>
              <div className="segmented" role="radiogroup" aria-labelledby="lv">
                {LEVELS.map(([name, v]) => (
                  <button type="button" key={name} role="radio" aria-checked={level === v} className={level === v ? "on" : ""} onClick={() => setLevel(v)}>{name}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <span>Language</span>
              <LanguagePicker onPick={setLanguage} />
              {languages.some((l) => !l.available) && (
                <small>C, C++ and Java need a code runner. Ask whoever runs this server to set it up. Python works everywhere.</small>
              )}
            </div>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary" disabled={busy || !topic.trim()} onClick={begin}>{busy ? "Writing your problem…" : "Start"}</button>
          </div>
        </main>
      )}

      {phase === "solve" && problem && (
        <div className="coding">
          <section className="problem">
            <div className="problem-head"><h2>{problem.title}</h2><span className="timer" aria-label="Time spent">{clock(seconds)}</span></div>
            <p className="statement">{problem.statement}</p>
            <h4>Examples</h4>
            {tests === null && <p className="hint">Preparing tests…</p>}
            {tests?.slice(0, 2).map((t, i) => <pre key={i}>{`Input:\n${t.input}Output:\n${t.expected}`}</pre>)}
            {problem.hints.slice(0, hints).map((h) => <p key={h} className="hint">Hint: {h}</p>)}
            {hints < problem.hints.length && <button className="link" onClick={() => setHints(hints + 1)}>Show a hint</button>}
          </section>

          <section className="editor">
            <LanguagePicker onPick={(id) => { setLanguage(id); setResults(null); setError(""); }} />
            <textarea className="code" spellCheck={false} aria-label={`Your ${label} code`} value={code}
              onChange={(e) => setCode(e.target.value)} onKeyDown={onKey} />
            <div className="actions">
              <button className="ghost" disabled={!canRun} onClick={run}>{running ? "Running…" : "Run tests"}</button>
              <button className="primary" disabled={!canRun} onClick={submit}>{busy ? "Reviewing…" : "Submit for review"}</button>
            </div>
            <p className="hint">
              Read from standard input, print to standard output.{language === "java" ? " Name your class Main." : ""} Tab indents; press Esc, then Tab, to leave the editor.
            </p>
            {error && <p className="error" role="alert">{error}</p>}
            {results?.fatal && <p className="error" role="alert" style={{ whiteSpace: "pre-wrap" }}>{results.fatal}</p>}
            {results?.results && (
              <div className="tests">
                <p><b>{passed} of {results.results.length} tests passed</b></p>
                <ul>
                  {results.results.map((r, i) => (
                    <li key={i} className={r.ok ? "pass" : "fail"}>
                      <span><b>{r.ok ? "Pass" : "Fail"}</b> <code>{clip(r.input.trim().replace(/\n/g, " ⏎ "), 60)}</code></span>
                      {!r.ok && <small>expected: {clip(r.expected, 120)} | got: {r.error || clip(r.got, 120) || "nothing printed"}</small>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </div>
      )}

      {phase === "done" && review && problem && (
        <main className="coding-wrap">
          <div className="score" style={{ color: BAND[review.band][1] }}>{review.score}</div>
          <p className="verdict">{BAND[review.band][0]}</p>
          <p className="meta">{label}: {review.passed} of {review.total} tests passed in {clock(seconds)}. Code quality {review.quality} out of 10.</p>
          {saved === "saved" && <p className="hint">Saved to your coding history.</p>}
          {saved === "failed" && <p className="error" role="alert">This attempt couldn’t be saved to your history.</p>}
          <h3>Complexity</h3>
          <p>{review.complexity}. {review.meets_expected_complexity ? "This matches the expected complexity." : `Expected: ${problem.expected_complexity}.`}</p>
          <section className="two">
            <div><h3>Strengths</h3><ul>{review.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>
            <div><h3>To improve</h3>{review.issues.length ? <ul>{review.issues.map((s) => <li key={s}>{s}</li>)}</ul> : <p>Nothing major.</p>}</div>
          </section>
          <h3>Next step</h3>
          <p>{review.next_step}</p>
          <h3>A follow-up an interviewer might ask</h3>
          <p className="summary">{review.follow_up_question}</p>
          <details><summary>Show the reference solution (Python)</summary><pre>{problem.reference_solution}</pre></details>
          <div className="actions">
            <button className="primary" onClick={() => { setPhase("setup"); setProblem(null); setError(""); }}>Try another problem</button>
            <a className="ghost" href="/coding/history">View history</a>
            <a className="ghost" href="/">Back to Rehearse</a>
          </div>
        </main>
      )}
    </div>
  );
}