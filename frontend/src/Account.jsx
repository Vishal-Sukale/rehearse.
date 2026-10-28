import { useEffect, useState } from "react";
import { deleteAccount, exportData } from "./api.js";

export default function Account({ user, onClose, onDeleted }) {
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const download = async () => {
    setBusy(true); setError("");
    try {
      const data = await exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      Object.assign(document.createElement("a"), { href: url, download: "rehearse-data.json" }).click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await deleteAccount(password);
      onDeleted();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="acct-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="acct-title">Your account</h2>
        <p className="sub">{user.name}, {user.email}</p>

        <h3>Your data</h3>
        <p className="hint">
          We store your account, your scorecards, the text of your answers, and your coding attempts (your code and the
          feedback). Unfinished interviews, including a summary of your resume if you used one, are kept for 7 days so you
          can continue them. Resume files aren’t stored.
        </p>
        <button className="ghost" disabled={busy} onClick={download}>Download my data (JSON)</button>

        <h3 className="danger-h">Delete account</h3>
        {!confirming ? (
          <>
            <p className="hint">Permanently deletes your account, every saved interview and every coding attempt. This can’t be undone.</p>
            <button className="ghost danger" onClick={() => setConfirming(true)}>Delete my account…</button>
          </>
        ) : (
          <form onSubmit={remove} className="form">
            <label className="field">
              <span>Enter your password to confirm</span>
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <div className="actions">
              <button className="primary danger-btn" disabled={busy || !password}>Delete everything</button>
              <button type="button" className="link" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </form>
        )}

        {error && <p className="error" role="alert">{error}</p>}
        <div className="actions"><button className="link" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}