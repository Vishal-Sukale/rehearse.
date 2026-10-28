// The signature element: difficulty rungs 1-5, one dot per answer, coloured by score.
// A hollow dot marks the question you're answering now.
const color = (s) => (s >= 7 ? "var(--good)" : s >= 4 ? "var(--warn)" : "var(--bad)");

export default function Ladder({ history, current, w = 260, h = 230 }) {
  const padL = 24, padR = 12, padT = 14, padB = 14;
  const step = (h - padT - padB) / 4;
  const y = (d) => padT + (5 - d) * step;
  const slots = Math.max(history.length + (current ? 1 : 0), 5);
  const dx = (w - padL - padR) / slots;
  const x = (i) => padL + dx * (i + 0.5);
  const pts = history.map((p, i) => [x(i), y(p.difficulty)]);
  const last = pts[pts.length - 1];
  const label = `Difficulty path: ${history.map((p) => p.difficulty).join(", ") || "no answers yet"}`;

  return (
    <svg className="ladder" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      {[1, 2, 3, 4, 5].map((d) => (
        <g key={d}>
          <line x1={padL} x2={w - padR} y1={y(d)} y2={y(d)} className="rung" />
          <text x={2} y={y(d) + 4} className="rung-label">{d}</text>
        </g>
      ))}
      {pts.length > 1 && <polyline className="path" points={pts.map((p) => p.join(",")).join(" ")} />}
      {current && last && (
        <line className="path dashed" x1={last[0]} y1={last[1]} x2={x(history.length)} y2={y(current)} />
      )}
      {history.map((p, i) => (
        <circle key={i} cx={pts[i][0]} cy={pts[i][1]} r="6" fill={color(p.score)}>
          <title>{`Difficulty ${p.difficulty}, scored ${p.score}/10`}</title>
        </circle>
      ))}
      {current && <circle className="here" cx={x(history.length)} cy={y(current)} r="6" />}
    </svg>
  );
}
