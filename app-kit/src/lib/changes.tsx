/**
 * Live changes (frontend/theme.md §10.3): which records just arrived or changed, so a
 * generated app can mark them, and a number that counts up when it changes.
 *
 * The page sends the keys ("<type>/<id>") of the records it just changed along with the
 * data (`demux:data` … `changed`); the runtime calls `noteData` before each render.
 * `changedClass(type, id)` then returns "demux-new" or "demux-updated" for HOLD_MS; the
 * runtime re-renders once the marks expire, so the classes go away and can play again.
 * The classes are styled here (a soft ring in the current text colour, and a 4px rise
 * for new records), so they suit any look. Reduced motion: nothing is marked.
 */
import * as React from "react";

export const HOLD_MS = 1600;

type Kind = "new" | "updated";
const marks = new Map<string, { kind: Kind; until: number }>();
let known: Set<string> | null = null;

function reduced(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function keysOf(data: unknown): Set<string> {
  const keys = new Set<string>();
  if (!data || typeof data !== "object") return keys;
  for (const [type, recs] of Object.entries(data as Record<string, unknown>)) {
    if (type.startsWith("_") || !recs || typeof recs !== "object") continue;
    for (const id of Object.keys(recs)) keys.add(`${type}/${id}`);
  }
  return keys;
}

/** Record the keys that changed with this data. Returns ms until the marks expire
 *  (0 when nothing is marked). The first data an app gets marks nothing. */
export function noteData(data: unknown, changed: unknown): number {
  const keys = keysOf(data);
  const now = Date.now();
  for (const [k, m] of marks) if (m.until <= now || !keys.has(k)) marks.delete(k);
  if (known && Array.isArray(changed) && !reduced()) {
    for (const k of changed) {
      if (typeof k === "string" && keys.has(k))
        marks.set(k, { kind: known.has(k) ? "updated" : "new", until: now + HOLD_MS });
    }
  }
  known = keys;
  let next = 0;
  for (const m of marks.values()) next = Math.max(next, m.until - now);
  return next;
}

/** "demux-new", "demux-updated" or "" for one record (`type`, `id`). */
export function changedClass(type: string, id: string): string {
  const m = marks.get(`${type}/${id}`);
  return m && m.until > Date.now() ? `demux-${m.kind}` : "";
}

export const CHANGES_CSS = `
@keyframes demux-ring { from { box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 30%, transparent); }
  to { box-shadow: 0 0 0 3px transparent; } }
@keyframes demux-rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
.demux-updated { animation: demux-ring ${HOLD_MS}ms ease-out; }
.demux-new { animation: demux-rise 240ms cubic-bezier(.16,1,.3,1), demux-ring ${HOLD_MS - 240}ms ease-out 240ms; }
@media (prefers-reduced-motion: reduce) { .demux-new, .demux-updated { animation: none; } }
`;

/** A number that counts from its previous value to the new one over `duration` ms. */
export function CountUp({
  value,
  format = (n: number) => Math.round(n).toLocaleString(),
  duration = 400,
  className,
}: {
  value: number;
  format?: (n: number) => React.ReactNode;
  duration?: number;
  className?: string;
}) {
  const [shown, setShown] = React.useState(value);
  const from = React.useRef(value);
  React.useEffect(() => {
    const start = from.current;
    from.current = value;
    if (!Number.isFinite(value) || !Number.isFinite(start) || start === value || reduced()) {
      setShown(value);
      return;
    }
    let frame = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / duration);
      const eased = 1 - (1 - k) ** 3;
      setShown(start + (value - start) * eased);
      if (k < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return <span className={["tabular-nums", className].filter(Boolean).join(" ")}>{format(shown)}</span>;
}
