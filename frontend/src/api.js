const KEY = "rehearse_token";
export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t) => localStorage.setItem(KEY, t);
export const clearToken = () => localStorage.removeItem(KEY);

async function call(url, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const isAuthCall = url.startsWith("/api/auth/login") || url.startsWith("/api/auth/signup");
  if (res.status === 401 && !isAuthCall) {
    clearToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    const d = e.detail;
    const err = new Error(typeof d === "string" ? d : "Something went wrong. Please check your details and try again.");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

// The resume file is sent as raw bytes; the server reads it and returns the parsed profile.
export async function uploadResume(file) {
  const headers = { "Content-Type": "application/octet-stream" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api/resume?filename=${encodeURIComponent(file.name)}`, { method: "POST", headers, body: file });
  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    const err = new Error(typeof e.detail === "string" ? e.detail : "We couldn't read that resume. Please try again.");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const health = () => call("/api/health");
export const signup = (name, email, password) => call("/api/auth/signup", { method: "POST", body: { name, email, password } });
export const login = (email, password) => call("/api/auth/login", { method: "POST", body: { email, password } });
export const me = () => call("/api/auth/me");
export const startInterview = (config) => call("/api/interviews", { method: "POST", body: config });
export const sendAnswer = (id, answer) => call(`/api/interviews/${id}/answer`, { method: "POST", body: { answer } });
export const endInterview = (id) => call(`/api/interviews/${id}/end`, { method: "POST", body: {} });
export const listInterviews = () => call("/api/interviews");
export const getInterview = (id) => call(`/api/interviews/${id}`);
export const deleteInterview = (id) => call(`/api/interviews/${id}`, { method: "DELETE" });
export const listLive = () => call("/api/interviews/live");
export const continueInterview = (id) => call(`/api/interviews/${id}/continue`, { method: "POST", body: {} });
export const discardLive = (id) => call(`/api/interviews/live/${id}`, { method: "DELETE" });
export const getStats = () => call("/api/stats");
export const exportData = () => call("/api/account/export");
export const deleteAccount = (password) => call("/api/account", { method: "DELETE", body: { password } });