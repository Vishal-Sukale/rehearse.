import { clearToken, getToken } from "./api.js";

export async function coachAnswer(interviewId, index) {
  const res = await fetch(`/api/interviews/${interviewId}/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ index }),
  });
  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Coaching isn't available right now. Please try again.");
  }
  return data;
}