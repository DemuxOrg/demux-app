"use client";

/**
 * The build card's progress (theme.md §7.10): a three-row checklist (rows 2 and 3 can
 * both be working: emails are read while the interface is designed) and the thinking
 * line under it.
 */
import { Check } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { STEPS, TOTAL, VERBS, type TrackState, type VerbPhase } from "./model";

const REDUCED = "(prefers-reduced-motion: reduce)";
function subscribeReduced(cb: () => void) {
  const q = window.matchMedia(REDUCED);
  q.addEventListener("change", cb);
  return () => q.removeEventListener("change", cb);
}
function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReduced,
    () => window.matchMedia(REDUCED).matches,
    () => false,
  );
}

export type ChecklistRow = { state: TrackState; detail: string };

const LABELS = [
  "Understanding your request",
  "Reading your emails",
  "Designing your interface",
] as const;

export function Checklist({
  step,
  rows,
}: {
  step: number;
  rows: [ChecklistRow, ChecklistRow, ChecklistRow];
}) {
  return (
    <ul
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={TOTAL}
      aria-valuenow={step}
      aria-valuetext={`Step ${step} of ${TOTAL}: ${STEPS[step - 1]}`}
      className="flex flex-col gap-0.5"
    >
      {rows.map((row, i) => (
        <li key={LABELS[i]} className="flex h-9 items-center gap-3">
          <span aria-hidden className="grid size-4 shrink-0 place-items-center">
            {row.state === "working" ? (
              <Spinner size={16} />
            ) : row.state === "done" ? (
              <span className="grid size-4 place-items-center rounded-full bg-violet text-white">
                <Check size={11} strokeWidth={3} />
              </span>
            ) : (
              <span className="size-4 rounded-full border-[1.5px] border-pending-line" />
            )}
          </span>
          <span
            className={`min-w-0 flex-1 truncate text-sm font-medium ${row.state === "waiting" ? "text-ink-3" : "text-ink"}`}
          >
            {LABELS[i]}
          </span>
          {row.detail && (
            <span className="shrink-0 text-[13px] text-ink-3 tabular">
              {row.detail}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

const VERB_MS = 2800;

/**
 * A verb that changes every 2.8 s with its letters rippling, then the latest real event.
 * Only the real part is announced (`aria-live`); the verbs are flavour (§7.10).
 */
export function ThinkingLine({
  phase,
  fact,
}: {
  phase: VerbPhase;
  fact: string | null;
}) {
  const reduced = useReducedMotion();
  const verbs = VERBS[phase];
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((x) => x + 1), VERB_MS);
    return () => clearInterval(t);
  }, []);
  const verb = `${verbs[n % verbs.length]}…`;

  return (
    <p className="mt-3 flex min-h-5 min-w-0 items-baseline gap-1.5 text-[13px]">
      <span aria-hidden className="shrink-0 font-medium text-ink-2">
        {reduced
          ? verb
          : [...verb].map((ch, i) => (
              <span
                key={`${verb}-${i}`}
                className="inline-block animate-dmx-ripple whitespace-pre"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {ch}
              </span>
            ))}
      </span>
      <span aria-live="polite" className="min-w-0 truncate text-ink-3">
        {fact ? `· ${fact}` : ""}
      </span>
    </p>
  );
}
