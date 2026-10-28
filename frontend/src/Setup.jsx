import { useRef, useState } from "react";
import { uploadResume } from "./api.js";

const TRACKS = {
  "Backend Engineer": ["Data structures & algorithms", "System design", "Databases & storage", "APIs & networking", "Concurrency & performance"],
  "Frontend Engineer": ["JavaScript & TypeScript", "React & state management", "Browser performance", "CSS & accessibility", "Testing"],
  "Full-Stack Engineer": ["APIs & networking", "Databases & storage", "React & state management", "System design", "Testing"],
  "Data Engineer": ["SQL", "Data modeling", "Pipelines & orchestration", "Distributed processing", "Data quality"],
  "ML Engineer": ["ML fundamentals", "Model evaluation", "MLOps & deployment", "Python & data tools", "System design"],
  "DevOps / SRE": ["Linux & networking", "CI/CD", "Containers & Kubernetes", "Observability & incidents", "Cloud infrastructure"],
};
const SENIORITY = ["junior", "mid", "senior", "staff"];
const ICONS = {
  "Backend Engineer": "⚙", "Frontend Engineer": "◧", "Full-Stack Engineer": "⬡",
  "Data Engineer": "≣", "ML Engineer": "∿", "DevOps / SRE": "⟳",
};
const DEFAULT_TRACK = "Backend Engineer";
const MAX_JOB_CHARS = 8000;

export default function Setup({ onStart, busy, error, mode, name }) {
  const [role, setRole] = useState(DEFAULT_TRACK);
  const [seniority, setSeniority] = useState("mid");
  const [topics, setTopics] = useState(TRACKS[DEFAULT_TRACK].slice(0, 3));
  const [custom, setCustom] = useState("");
  const [count, setCount] = useState(5);
  const [practice, setPractice] = useState(true);
  const [resume, setResume] = useState(null);
  const [job, setJob] = useState("");
  const [reading, setReading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [drag, setDrag] = useState(false);
  const fileRef = useRef(null);

  const pickTrack = (t) => { setRole(t); setTopics(TRACKS[t].slice(0, 3)); };

  const handleFile = async (file) => {
    if (!file) return;
    setUploadError("");
    if (file.size > 5 * 1024 * 1024) { setUploadError("That file is larger than 5 MB."); return; }
    setReading(true);
    try {
      const p = await uploadResume(file);
      setResume(p);
      if (p.suggested_role) setRole(p.suggested_role);
      if (p.suggested_seniority) setSeniority(p.suggested_seniority);
      setTopics(p.skills?.length ? p.skills.slice(0, 4) : [p.suggested_role || "General engineering"]);
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setReading(false);
    }
  };

  const removeResume = () => {
    setResume(null); setUploadError("");
    setRole(DEFAULT_TRACK); setTopics(TRACKS[DEFAULT_TRACK].slice(0, 3));
  };

  const suggested = resume ? resume.skills : (TRACKS[role] || TRACKS[DEFAULT_TRACK]);
  const all = [...suggested, ...topics.filter((t) => !suggested.includes(t))];
  const toggle = (t) => setTopics((c) => (c.includes(t) ? c.filter((x) => x !== t) : [...c, t]));
  const addCustom = () => { const t = custom.trim(); if (t && !topics.includes(t)) setTopics([...topics, t]); setCustom(""); };
  const ready = role.trim() && topics.length > 0 && !busy && !reading;

  const summary = resume && [
    resume.years_experience != null ? `${resume.years_experience} years of experience` : null,
    `${resume.skills.length} skills`,
    `${resume.experience.length} roles`,
    `${resume.projects.length} projects`,
  ].filter(Boolean).join(", ");

  return (
    <div className="page">
      <h1 className="welcome"><span className="grad">Hello, {name.split(" ")[0]}.</span><br />Ready to practice?</h1>
      <p className="lead">Choose a track, upload your resume, or paste a job description and get interviewed for that exact role.</p>
      {mode === "offline" && <p className="note">Demo mode: answers are scored by length, with no AI model behind them.</p>}
      {mode === "down" && <p className="note bad">The backend isn’t reachable. Start it on port 8000.</p>}

      <form className="form" onSubmit={(e) => {
        e.preventDefault();
        ready && onStart({
          role: role.trim(), seniority, topics, max_questions: count, practice_mode: practice,
          ...(resume ? { resume } : {}),
          ...(job.trim() ? { job_description: job.trim() } : {}),
        });
      }}>
        <div className="field">
          <span>Interview on your resume (optional)</span>
          {resume ? (
            <div className="resume-card">
              <div>
                <b>{resume.name || "Your resume"}</b>
                <p>{resume.headline}</p>
                <p>{summary}.</p>
              </div>
              <button type="button" className="link" onClick={removeResume}>Remove</button>
            </div>
          ) : (
            <>
              <button type="button" className={`drop ${drag ? "over" : ""}`} disabled={reading}
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files?.[0]); }}>
                <b>{reading ? "Reading your resume…" : "Upload your resume"}</b>
                <small>
                  PDF, DOCX or TXT, up to 5 MB. Drop it here or click to choose. The text is sent to the AI model to
                  write your questions; the file itself isn’t stored.
                </small>
              </button>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md" hidden
                onChange={(e) => { handleFile(e.target.files?.[0]); e.target.value = ""; }} />
            </>
          )}
          {uploadError && <p className="error" role="alert">{uploadError}</p>}
          {resume && <p className="hint">Every question will be based on your experience and projects. Pick the skills to focus on below.</p>}
        </div>

        <label className="field">
          <span>Target a specific job (optional)</span>
          <textarea rows={5} maxLength={MAX_JOB_CHARS} value={job} onChange={(e) => setJob(e.target.value)}
            placeholder="Paste the job description here. Questions will follow what this employer asks for." />
          <small>
            {job.length > 0 ? `${job.length} of ${MAX_JOB_CHARS} characters. ` : ""}
            Works best with the role, requirements and tech stack. Combine it with your resume to practise the gaps.
          </small>
        </label>

        {!resume && (
          <div className="field">
            <span>Or choose a track</span>
            <div className="tracks">
              {Object.keys(TRACKS).map((t) => (
                <button type="button" key={t} aria-pressed={role === t}
                  className={role === t ? "track-card on" : "track-card"} onClick={() => pickTrack(t)}>
                  <span className="ico" aria-hidden>{ICONS[t]}</span>{t}
                </button>
              ))}
            </div>
          </div>
        )}

        <label className="field"><span>Role (edit it to match the job)</span>
          <input value={role} maxLength={80} onChange={(e) => setRole(e.target.value)} /></label>
        <div className="field">
          <span id="lvl">Your level</span>
          <div className="segmented" role="radiogroup" aria-labelledby="lvl">
            {SENIORITY.map((s) => (
              <button type="button" key={s} role="radio" aria-checked={seniority === s} className={seniority === s ? "on" : ""} onClick={() => setSeniority(s)}>{s}</button>
            ))}
          </div>
        </div>
        <div className="field">
          <span>{resume ? "Skills to focus on" : "Topics to cover"}</span>
          <div className="chips">
            {all.map((t) => (
              <button type="button" key={t} aria-pressed={topics.includes(t)} className={topics.includes(t) ? "chip on" : "chip"} onClick={() => toggle(t)}>{t}</button>
            ))}
          </div>
          <div className="addrow">
            <input placeholder="Add your own topic" value={custom} onChange={(e) => setCustom(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } }} />
            <button type="button" className="ghost" onClick={addCustom}>Add topic</button>
          </div>
        </div>
        <label className="field"><span>Questions: <b>{count}</b></span>
          <input type="range" min="3" max="10" value={count} onChange={(e) => setCount(+e.target.value)} /></label>
        <label className="check">
          <input type="checkbox" checked={practice} onChange={(e) => setPractice(e.target.checked)} />
          <span>Show feedback after each answer<small>Turn off to simulate a real interview.</small></span>
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={!ready}>{busy ? "Preparing your first question…" : "Start interview"}</button>
      </form>
    </div>
  );
}