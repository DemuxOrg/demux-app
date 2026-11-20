/** Spinner (theme.md §7.10, §9): magenta arc on a magenta-soft track, 0.9s linear. */
export function Spinner({
  size = 22,
  light = false,
}: {
  size?: number;
  light?: boolean;
}) {
  const stroke = size >= 20 ? 2.5 : 2;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0 animate-dmx-spin"
      aria-hidden
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
        className={light ? "stroke-white/35" : "stroke-magenta-soft"}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${c * 0.28} ${c}`}
        className={light ? "stroke-white" : "stroke-magenta"}
      />
    </svg>
  );
}
