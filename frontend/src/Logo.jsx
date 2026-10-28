import { useId } from "react";

export default function Logo({ size = 32, name = true }) {
  const id = useId().replace(/:/g, "");
  return (
    <span className="logo" style={{ "--s": `${size}px` }}>
      <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop stopColor="#7FB2FF" />
            <stop offset="1" stopColor="#B58CFF" />
          </linearGradient>
        </defs>
        <path fill={`url(#${id})`} d="M8 6h32a6 6 0 0 1 6 6v18a6 6 0 0 1-6 6H24l-9 8v-8H8a6 6 0 0 1-6-6V12a6 6 0 0 1 6-6z" />
        <rect x="13" y="24" width="5" height="7" rx="1.5" fill="#0c0e22" />
        <rect x="21.5" y="19" width="5" height="12" rx="1.5" fill="#0c0e22" />
        <rect x="30" y="13" width="5" height="18" rx="1.5" fill="#0c0e22" />
      </svg>
      {name && <span className="wordmark">Rehearse</span>}
    </span>
  );
}