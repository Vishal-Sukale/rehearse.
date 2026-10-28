import { useCallback, useEffect, useRef, useState } from "react";

const SR = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
export const voiceSupport = {
  listen: Boolean(SR),
  speak: typeof window !== "undefined" && "speechSynthesis" in window,
};

const LANG = typeof navigator !== "undefined" && /^en/i.test(navigator.language) ? navigator.language : "en-US";

const BLOCKED =
  "Microphone access is blocked. Click the lock icon in the address bar, set Microphone to Allow, then press the mic again. " +
  "Also check Windows Settings > Privacy & security > Microphone.";
const noMic = (seen) =>
  (seen === 0
    ? "Your browser can't see any microphone. "
    : `Your browser sees ${seen} microphone(s) but none respond. `) +
  "Open Windows Settings > System > Sound > Input: a microphone should be listed and its volume bar should move when you speak. " +
  "If it's missing, plug in a headset, or enable it under Sound settings > Recording > right-click > Show disabled devices. " +
  "If you're using headphones without a mic, unplug them or pick another input.";
const MESSAGES = {
  "not-allowed": BLOCKED,
  "service-not-allowed": BLOCKED,
  "audio-capture": noMic(0),
  "no-speech": "I didn't hear anything. Check that the right microphone is selected, then try again.",
  network:
    "Speech recognition couldn't reach its online service. Check your internet connection, and use Chrome or Edge (Brave and Firefox don't support it).",
  "language-not-supported": "Your browser doesn't support speech recognition for this language.",
};

// Asking for the mic directly gives a clear permission prompt and a precise error.
// If the default input is dead, every other input the browser lists is tried too.
async function checkMic() {
  const md = typeof navigator !== "undefined" ? navigator.mediaDevices : null;
  if (!md?.getUserMedia) return "This page can't use the microphone. Open it at http://localhost:5173 in Chrome or Edge.";
  const open = async (audio) => (await md.getUserMedia({ audio })).getTracks().forEach((t) => t.stop());
  try {
    await open(true);
    return null;
  } catch (first) {
    if (first.name === "NotReadableError") {
      return "Your microphone is in use by another app or isn't responding. Close apps that use it (Teams, Zoom, Discord) and try again.";
    }
    if (first.name !== "NotFoundError" && first.name !== "OverconstrainedError") return BLOCKED;
    let inputs = [];
    try {
      inputs = (await md.enumerateDevices()).filter((d) => d.kind === "audioinput" && d.deviceId);
    } catch { /* ignore */ }
    for (const d of inputs) {
      try {
        await open({ deviceId: { exact: d.deviceId } });
        return `Your browser's default microphone isn't responding, but "${d.label || "another input"}" works. ` +
          "Open your browser's microphone setting (Settings > Privacy and security > Site settings > Microphone), choose that device, then try again.";
      } catch { /* try the next one */ }
    }
    return noMic(inputs.length);
  }
}

/**
 * Speech in and out (browser built-ins, no server or key needed).
 *  - start(existingText): dictate; onText receives the live transcript. Errors appear in `error`.
 *  - onSilence(text) fires after `silenceMs` of quiet (used by hands-free mode).
 *  - speak(text, onDone): read aloud. onDone is skipped if the speech was cancelled.
 */
export function useVoice({ onText, onSilence, silenceMs = 2500 }) {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState("");
  const rec = useRef(null);
  const wanted = useRef(false);     // true while the user wants the mic on
  const starting = useRef(false);
  const restarts = useRef(0);       // restarts with nothing heard
  const latest = useRef("");
  const base = useRef("");
  const timer = useRef(null);
  const speechId = useRef(0);
  const cbs = useRef({});
  cbs.current = { onText, onSilence };

  const begin = useCallback(() => {
    const r = new SR();
    r.lang = LANG;
    r.continuous = true;
    r.interimResults = true;
    base.current = latest.current ? `${latest.current} ` : "";
    r.onresult = (e) => {
      restarts.current = 0;
      let heard = "";
      for (let i = 0; i < e.results.length; i++) heard += e.results[i][0].transcript;
      const full = (base.current + heard).trim();
      latest.current = full;
      cbs.current.onText?.(full);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => cbs.current.onSilence?.(full), silenceMs);
    };
    r.onerror = (e) => {
      if (e.error === "aborted" || e.error === "no-speech") return;   // no-speech is handled in onend
      wanted.current = false;
      setError(MESSAGES[e.error] || `Speech recognition error: ${e.error}`);
    };
    r.onend = () => {
      clearTimeout(timer.current);
      rec.current = null;
      // Chrome ends sessions on its own after silence; quietly restart a few times before giving up.
      if (wanted.current && restarts.current < 3) {
        restarts.current += 1;
        try { begin(); return; } catch { /* fall through and stop */ }
      }
      if (wanted.current) setError(MESSAGES["no-speech"]);
      wanted.current = false;
      setListening(false);
    };
    rec.current = r;
    r.start();
  }, [silenceMs]);

  const start = useCallback(async (existing = "") => {
    if (!SR || wanted.current || starting.current) return;
    starting.current = true;
    setError("");
    try {
      const problem = await checkMic();
      if (problem) { setError(problem); return; }
      wanted.current = true;
      restarts.current = 0;
      latest.current = existing.trim();
      begin();
      setListening(true);
    } catch {
      wanted.current = false;
      setError("Couldn't start the microphone. Please try again.");
    } finally {
      starting.current = false;
    }
  }, [begin]);

  const stop = useCallback(() => {
    wanted.current = false;
    clearTimeout(timer.current);
    rec.current?.stop();
    setListening(false);
  }, []);

  const cancel = useCallback(() => {
    speechId.current += 1;                 // invalidates any pending onDone
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  const speak = useCallback((text, onDone) => {
    if (!voiceSupport.speak) { onDone?.(); return; }
    const id = ++speechId.current;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const nice = window.speechSynthesis.getVoices().find((v) => /^en/i.test(v.lang) && /natural|google|samantha|aria|jenny/i.test(v.name));
    if (nice) u.voice = nice;
    u.onstart = () => setSpeaking(true);
    const finish = () => { setSpeaking(false); if (id === speechId.current) onDone?.(); };
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
  }, []);

  useEffect(() => () => {
    wanted.current = false;
    clearTimeout(timer.current);
    rec.current?.abort?.();
    window.speechSynthesis?.cancel();
  }, []);

  return { listening, speaking, error, clearError: () => setError(""), start, stop, speak, cancel };
}