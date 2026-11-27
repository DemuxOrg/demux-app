/**
 * What the build card shows, derived from the run's real events (theme.md §7.10). Steps 2 and 3 run side by side in the backend: emails are read
 * while the interface designer works, so each has its own track.
 */
import type { RunEvent } from "@/lib/api";

export const STEPS = [
  "Your request",
  "Reading your emails",
  "Building your workspace",
] as const;
export const TOTAL = STEPS.length;

export type TrackState = "waiting" | "working" | "done";
export type Progress = { done: number; total: number };
export type VerbPhase = "request" | "reading" | "designing";

/** Designer events (backend `app/agent/designer.py`) as the track shows them. */
const DESIGNER: Record<string, { label: string; done: boolean }> = {
  "Designing the interface": { label: "", done: false },
  "Redesigning the interface": { label: "", done: false },
  "Interface check failed, fixing": { label: "Fixing a check", done: false },
  "Adjusting the interface to your data": {
    label: "Checking it with your data",
    done: false,
  },
  "Interface ready": { label: "", done: true },
};

export function plural(n: number, noun: string): string {
  const word = noun.replace(/_/g, " ");
  return `${n} ${n === 1 || word.endsWith("s") ? word : `${word}s`}`;
}

export function readingProgress(events: RunEvent[]): Progress | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.phase === "process" && e.total != null && e.done != null)
      return { done: e.done, total: e.total };
  }
  return null;
}

export function readingTrack(
  events: RunEvent[],
  progress: Progress | null,
): TrackState {
  if (progress && progress.total > 0 && progress.done >= progress.total)
    return "done";
  if (progress && progress.total === 0) return "done";
  return events.some((e) => e.phase === "process") ? "working" : "waiting";
}

export function designerTrack(events: RunEvent[]): {
  state: TrackState;
  label: string;
} {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.phase !== "app") continue;
    const known = DESIGNER[e.label];
    if (known)
      return { state: known.done ? "done" : "working", label: known.label };
    // "Used a simple list view…": the build fell back to the default app.
    if (e.label.startsWith("Used a simple"))
      return { state: "done", label: "" };
  }
  return { state: "waiting", label: "" };
}

/** The latest event worth reading in the thinking line (progress lives in the tracks). */
export function latestEvent(events: RunEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const l = events[i].label;
    if (!l.startsWith("Reading your emails")) return l;
  }
  return null;
}

export const VERBS: Record<VerbPhase, string[]> = {
  request: [
    "Reading your request",
    "Searching your inbox",
    "Sampling threads",
    "Spotting patterns",
  ],
  reading: [
    "Untangling threads",
    "Sorting",
    "Matching replies",
    "Cross-checking dates",
    "Tallying amounts",
  ],
  designing: [
    "Sketching the layout",
    "Choosing a palette",
    "Setting the numbers",
    "Polishing",
  ],
};
