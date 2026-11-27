/**
 * What the build card shows, derived from the run's real events (theme.md §7.10). Steps 2 and 3 run side by side in the backend: emails are read
 * while the interface designer works, so each has its own track.
 */
import type { RunEvent, SetupState } from "@/lib/api";

export type TrackState = "waiting" | "working" | "done";
export type Progress = { done: number; total: number };

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

/** The live build strip's line (theme.md §7.10), from the run's events and counts. */
export function stripLine(
  events: RunEvent[],
  recordCounts: Record<string, number>,
): string {
  const progress = readingProgress(events);
  const reading = readingTrack(events, progress);
  if (reading === "waiting") return "Looking through your mail";
  if (reading === "working") {
    const parts = ["Reading your emails"];
    if (progress)
      parts.push(`${progress.done} of ${plural(progress.total, "thread")}`);
    const top = Object.entries(recordCounts)
      .filter(([t]) => !t.startsWith("_"))
      .sort((a, b) => b[1] - a[1])[0];
    if (top) parts.push(`${plural(top[1], top[0])} found`);
    return parts.join(" · ");
  }
  const last = [...events].reverse().find((e) => e.phase === "app")?.label;
  return last === "Adjusting the interface to your data"
    ? "Checking it against your data"
    : "Building the interface";
}

/** Threads read ÷ threads found, 0–1 (1 once reading is done). */
export function readingShare(events: RunEvent[]): number {
  const progress = readingProgress(events);
  if (readingTrack(events, progress) === "done") return 1;
  return progress?.total ? progress.done / progress.total : 0;
}

/** One question moment (theme.md §7.15). */
export type Moment = {
  key: string;
  kind: "look" | "question";
  id: string;
  question: string;
  options: string[];
  recommended: number;
};

/** Mirrors backend `app/agent/look.py` (LOOK_OPTIONS): directions, never palettes. */
export const LOOK_MOMENT: Moment = {
  key: "look",
  kind: "look",
  id: "look",
  question: "How should your workspace look?",
  options: [
    "Let Demux decide",
    "Light and calm",
    "Dark and focused",
    "Bold and colourful",
  ],
  recommended: 0,
};

/** The moments still waiting for the user, in order: the look, then each clarifying
 *  question not answered yet (`sent`: answered here, ahead of the next poll). */
export function pendingMoments(
  setup: SetupState | null | undefined,
  sent: ReadonlySet<string>,
): Moment[] {
  if (!setup) return [];
  const out: Moment[] = [];
  if (setup.look_state === "asking" && !sent.has("look")) out.push(LOOK_MOMENT);
  if (setup.questions_state === "asking") {
    const done = new Set(setup.answered_ids ?? []);
    for (const q of setup.questions) {
      if (done.has(q.id) || sent.has(q.id)) continue;
      out.push({
        key: q.id,
        kind: "question",
        id: q.id,
        question: q.question,
        options: q.options,
        recommended: q.recommended,
      });
    }
  }
  return out;
}

/** Nothing more is needed from the user (§7.10 strip's second line). */
export function userPartDone(setup: SetupState | null | undefined): boolean {
  if (!setup) return false;
  return (
    setup.look_state !== "asking" &&
    ["answered", "timed_out", "none"].includes(setup.questions_state)
  );
}
