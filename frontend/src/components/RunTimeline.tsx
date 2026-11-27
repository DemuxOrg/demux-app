/**
 * Compact live view of a running sync or edit (the build has its own live view, LiveBuild in WorkspaceDetail):
 * the current phase with a spinner, then its latest few events.
 */
import { Spinner } from "@/components/ui/Spinner";
import type { RunEvent } from "@/lib/api";

const PHASES: Record<string, string> = {
  design: "Understanding your request",
  process: "Reading your emails",
  app: "Building the interface",
  edit: "Working on your request",
};

export function RunTimeline({ events }: { events: RunEvent[] }) {
  const last = events[events.length - 1];
  if (!last)
    return (
      <p className="flex items-center gap-2.5 text-sm text-ink-2">
        <Spinner size={16} /> Starting…
      </p>
    );
  const recent = events.filter((e) => e.phase === last.phase).slice(-3);
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <p className="flex items-center gap-2.5 text-sm font-semibold">
        <Spinner size={16} />
        {PHASES[last.phase] ?? last.phase}
      </p>
      <ul className="ml-[26px] flex flex-col gap-1">
        {recent
          .filter((e) => e.label !== PHASES[e.phase])
          .map((e, i) => (
            <li key={`${e.t}-${i}`} className="text-[13px] text-ink-2">
              {e.label}
            </li>
          ))}
      </ul>
    </div>
  );
}
