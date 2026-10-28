import { useState } from "react";
import Logo from "./Logo.jsx";
import { login, setToken, signup } from "./api.js";

const FEATURES = [
  ["↗", "Adaptive difficulty", "Questions get harder when you do well and ease off when you struggle."],
  ["✓", "Answers checked twice", "Every grade is verified against a fact-checked reference answer."],
  ["◉", "Talk, don’t type", "Answer out loud with built-in voice input and a hands-free mode."],
];

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const switchTo = (m) => { setMode(m); setError(""); };

  const validate = () => {
    if (!isLogin && !f.name.trim()) return "Please enter your name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) return "Please enter a valid email address, like name@example.com.";
    if (!f.password) return "Please enter your password.";
    if (!isLogin && f.password.length < 8) return "Your password must be at least 8 characters.";
    return "";
  };

  const submit = async (e) => {
    e.preventDefault();
    const problem = validate();
    if (problem) { setError(problem); return; }
    setBusy(true);
    setError("");
    try {
      const email = f.email.trim();
      const r = isLogin ? await login(email, f.password) : await signup(f.name.trim(), email, f.password);
      setToken(r.token);
      onAuth(r.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <section className="auth-pitch">
        <Logo size={40} />
        <h1>Practice interviews with an <span className="grad">AI that listens.</span></h1>
        <div className="feats">
          {FEATURES.map(([icon, title, text]) => (
            <div className="feat" key={title}>
              <span className="feat-ico" aria-hidden>{icon}</span>
              <div><b>{title}</b><p>{text}</p></div>
            </div>
          ))}
        </div>
        <div className="preview" aria-hidden>
          <p className="q">How would you design a rate limiter for a public API?</p>
          <p className="a">I’d use a token bucket per API key, stored in Redis…</p>
          <p className="s">Scored 8.4 out of 10</p>
        </div>
      </section>

      <form className="auth-card" onSubmit={submit} noValidate>
        <div className="segmented tabs" role="tablist">
          <button type="button" role="tab" aria-selected={isLogin} className={isLogin ? "on" : ""} onClick={() => switchTo("login")}>Sign in</button>
          <button type="button" role="tab" aria-selected={!isLogin} className={!isLogin ? "on" : ""} onClick={() => switchTo("signup")}>Create account</button>
        </div>
        <div>
          <h2>{isLogin ? "Welcome back" : "Start practicing"}</h2>
          <p className="sub">{isLogin ? "Sign in to continue your interview history." : "Create a free account to save your scorecards."}</p>
        </div>
        {!isLogin && (
          <label className="field"><span>Your name</span>
            <input maxLength={60} autoComplete="name" value={f.name} onChange={set("name")} /></label>
        )}
        <label className="field"><span>Email</span>
          <input type="email" autoComplete="email" value={f.email} onChange={set("email")} /></label>
        <label className="field"><span>Password</span>
          <div className="pw">
            <input type={show ? "text" : "password"}
              autoComplete={isLogin ? "current-password" : "new-password"} value={f.password} onChange={set("password")} />
            <button type="button" className="link" onClick={() => setShow(!show)}>{show ? "Hide" : "Show"}</button>
          </div>
          {!isLogin && <small>At least 8 characters.</small>}
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}</button>
      </form>
    </div>
  );
}