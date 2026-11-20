/**
 * The Demux mark and lockup (theme.md §2). The mark is inlined so it renders crisply at
 * every size; `useId` keeps gradient ids unique when it appears more than once.
 */
import { useId } from "react";

export function LogoMark({
  size = 28,
  className = "",
  title,
}: {
  size?: number;
  className?: string;
  title?: string;
}) {
  const id = useId().replace(/:/g, "");
  const g = (n: string) => `${id}-${n}`;
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <defs>
        <linearGradient id={g("ring")} x1="0.35" y1="0" x2="0.6" y2="1">
          <stop offset="0" stopColor="#7A35E6" />
          <stop offset="0.55" stopColor="#B83FAF" />
          <stop offset="1" stopColor="#E04E72" />
        </linearGradient>
        <linearGradient id={g("b1")} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#8A3FE8" />
          <stop offset="1" stopColor="#5B3BF0" />
        </linearGradient>
        <linearGradient id={g("b2")} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#9B3FD0" />
          <stop offset="1" stopColor="#DE3773" />
        </linearGradient>
        <linearGradient id={g("b3")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#D2477A" />
          <stop offset="1" stopColor="#F26A3A" />
        </linearGradient>
      </defs>
      <circle
        cx="50"
        cy="50"
        r="43.5"
        fill="#FFFFFF"
        stroke={`url(#${g("ring")})`}
        strokeWidth="4.6"
      />
      <path
        d="M29 52 L63.2 62.2 Q67.8 63.8 67.2 69.4 Q66.5 74.6 61.8 72.8 Z"
        fill={`url(#${g("b3")})`}
      />
      <path
        d="M29 51.5 L66.6 45.6 Q71.4 45 71.4 51.4 Q71.4 57.8 66.6 57.4 Z"
        fill={`url(#${g("b2")})`}
      />
      <path
        d="M29 51 L60.8 29.6 Q65.4 26.8 66.9 31.4 Q68 35.6 64.6 38.8 Z"
        fill={`url(#${g("b1")})`}
      />
    </svg>
  );
}

/** Mark + wordmark. Gap = 0.35 × mark, wordmark ≈ 0.68 × mark (28px → 10px gap, 19px). */
export function Lockup({ size = 28 }: { size?: number }) {
  return (
    <span
      className="inline-flex items-center"
      style={{ gap: Math.round(size * 0.35) }}
    >
      <LogoMark size={size} />
      <span
        className="font-semibold tracking-[-0.02em] text-ink"
        style={{ fontSize: Math.round(size * 0.68) }}
      >
        Demux
      </span>
    </span>
  );
}
