/**
 * Live timeline of a run's events, grouped by phase:
 * Understanding your request → Reading your emails → Building the interface.
 */
import type { RunEvent } from "@/lib/api";

const PHASES: Record<string, string> = {
  design: "Understanding your request",
  process: "Reading your emails",
  app: "Building the interface",
  edit: "Working on your request",
};

export function RunTimeline({
  events,
  compact = false,
}: {
  events: RunEvent[];
  compact?: boolean;
}) {
  const groups: { phase: string; events: RunEvent[] }[] = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    if (last && last.phase === e.phase) last.events.push(e);
    else groups.push({ phase: e.phase, events: [e] });
  }
  if (!groups.length)
    return <p className="text-sm text-gray-500">Waiting for the worker…</p>;
  return (
    <ol className="space-y-3">
      {groups.map((g, i) => {
        const current = i === groups.length - 1;
        const shown = compact ? g.events.slice(-3) : g.events.slice(-12);
        return (
          <li key={i}>
            <p
              className={`text-sm font-medium ${current ? "text-blue-700" : "text-gray-500"}`}
            >
              {current ? "◌ " : "✓ "}
              {PHASES[g.phase] ?? g.phase}
            </p>
            {(current || !compact) && (
              <ul className="mt-1 space-y-0.5 border-l border-gray-200 pl-3">
                {shown.map((e, j) => (
                  <li key={j} className="text-xs text-gray-600">
                    {e.label}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
