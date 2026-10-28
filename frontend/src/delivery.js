// Deterministic speaking-delivery metrics. No AI involved, so it is instant, free and works offline.
const FILLERS = ["um", "uh", "er", "erm", "you know", "i mean", "sort of", "kind of", "basically", "literally"];
const HEDGES = ["i think", "i guess", "i believe", "maybe", "perhaps", "probably", "not sure", "might be"];

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const count = (phrase, text) => (text.match(new RegExp(`\\b${escape(phrase)}\\b`, "g")) || []).length;
const sum = (obj) => Object.values(obj).reduce((a, b) => a + b, 0);

export function analyzeDelivery(answer) {
  const text = (answer || "").toLowerCase();
  const words = (text.match(/[a-z0-9']+/g) || []).length;
  const tally = (list) => Object.fromEntries(list.map((p) => [p, count(p, text)]).filter(([, c]) => c > 0));
  const fillerDetail = tally(FILLERS);
  return {
    words,
    length: words < 40 ? "short" : words > 300 ? "long" : "good",
    fillers: sum(fillerDetail),
    fillerDetail,
    hedges: sum(tally(HEDGES)),
    numbers: (text.match(/\b\d[\d,.]*%?/g) || []).length,
  };
}

export function summarizeDelivery(answers) {
  const items = answers.map(analyzeDelivery).filter((a) => a.words > 0);
  if (items.length === 0) return null;
  const total = (key) => items.reduce((s, a) => s + a[key], 0);
  const words = total("words"), fillers = total("fillers"), hedges = total("hedges"), numbers = total("numbers");
  const avgWords = Math.round(words / items.length);
  const fillerRate = Math.round((1000 * fillers) / words) / 10;   // per 100 words, one decimal
  const tips = [];
  if (fillerRate >= 2) tips.push("Pause silently instead of saying “um”, “you know” or “basically”. A short pause sounds confident.");
  if (hedges >= items.length) tips.push("You often soften statements with “I think” or “maybe”. State your answer first, then explain your reasoning.");
  if (avgWords < 50) tips.push("Your answers are short. Add your reasoning, a trade-off and an example.");
  if (avgWords > 250) tips.push("Your answers run long. Lead with the conclusion, then support it in two or three points.");
  if (numbers === 0) tips.push("Add numbers (scale, latency, cost, impact) to make your answers concrete.");
  return { answers: items.length, avgWords, fillers, fillerRate, hedges, numbers, tips };
}