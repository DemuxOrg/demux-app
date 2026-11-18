/**
 * Build progress card (theme.md §7.10): breathing logo, the quoted prompt, and the three
 * fixed phases as steps (done / active / pending). The active step shows the latest
 * event as a live line and, while emails are read in batches, a progress bar filled
 * with the brand gradient (one of the two places that gradient is allowed).
 *
 * Reading emails and writing the interface run in parallel in the backend; the card
 * shows "Reading your emails" as active until every batch is read.
 */
import { Check } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Spinner } from "@/components/ui/Spinner";
import type { RunEvent } from "@/lib/api";

const STEPS = [
  { phase: "design", label: "Understanding your request" },
  { phase: "process", label: "Reading your emails" },
  { phase: "app", label: "Building the interface" },
] as const;

const BATCHES = /\((\d+) of (\d+) batches\)/;
const THREADS = /\((\d+) threads\)$/;

function analyse(events: RunEvent[]) {
  const seen = new Set(events.map((e) => e.phase));
  let batch: { done: number; total: number } | null = null;
  for (const e of events) {
    const m = e.phase === "process" ? BATCHES.exec(e.label) : null;
    if (m) batch = { done: Number(m[1]), total: Number(m[2]) };
  }
  const readingDone = batch !== null && batch.done >= batch.total;
  let active = 0;
  if (seen.has("process") && !readingDone) active = 1;
  else if (seen.has("app") || readingDone) active = 2;
  else if (seen.has("process")) active = 1;
  const phase = STEPS[active].phase;
  // The batch count is already on the right; the live line says what else happened.
  const last = [...events]
    .reverse()
    .find((e) => e.phase === phase && !BATCHES.test(e.label));
  const threads = last && THREADS.exec(last.label);
  const live = threads
    ? `Found ${threads[1]} matching email threads`
    : (last?.label ?? null);
  return { active, batch: active === 1 ? batch : null, live };
}

export function BuildProgress({
  prompt,
  events,
}: {
  prompt: string;
  events: RunEvent[];
}) {
  const { active, batch, live } = analyse(events);
  const pct = batch
    ? Math.max(6, Math.round((batch.done / Math.max(1, batch.total)) * 100))
    : null;

  return (
    <section className="w-full max-w-[620px] rounded-2xl bg-surface px-7 pt-9 pb-6 shadow-float sm:px-9">
      <LogoMark size={56} className="animate-dmx-breathe" />
      <h1 className="mt-6 text-[30px] leading-[1.1] font-medium tracking-[-0.03em]">
        Building your workspace
      </h1>
      <p className="mt-2 line-clamp-3 text-base text-ink-2">“{prompt}”</p>

      <ol className="mt-6 border-t border-line-soft">
        {STEPS.map((s, i) => {
          const state =
            i < active ? "done" : i === active ? "active" : "pending";
          return (
            <li
              key={s.phase}
              className="border-b border-line-soft py-4"
              aria-current={state === "active" ? "step" : undefined}
            >
              <div className="flex items-center gap-3">
                <span className="grid size-7 shrink-0 place-items-center">
                  {state === "done" ? (
                    <span className="grid size-7 place-items-center rounded-full bg-violet-soft text-violet">
                      <Check size={16} strokeWidth={2.4} aria-hidden />
                    </span>
                  ) : state === "active" ? (
                    <Spinner size={22} />
                  ) : (
                    <span className="size-6 rounded-full border-2 border-pending-line" />
                  )}
                </span>
                <span
                  className={`flex-1 text-base ${
                    state === "active"
                      ? "font-semibold"
                      : state === "done"
                        ? "font-medium"
                        : "font-medium text-ink-3"
                  }`}
                >
                  {s.label}
                </span>
                {state === "done" && (
                  <span className="text-[13px] text-ink-3">Done</span>
                )}
                {state === "active" && batch && (
                  <span className="text-[13px] text-ink-2 tabular">
                    Batch {batch.done} of {batch.total}
                  </span>
                )}
              </div>
              {state === "active" && (
                <div className="mt-3 ml-10 flex flex-col gap-2.5 animate-dmx-rise">
                  {i === 1 && (
                    <div
                      role="progressbar"
                      aria-label="Reading your emails"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={pct ?? undefined}
                      className="h-1.5 overflow-hidden rounded-full bg-track"
                    >
                      <div
                        className="h-full animate-dmx-flow rounded-full bg-brand-flow transition-[width] duration-500 ease-dmx"
                        style={{ width: `${pct ?? 12}%` }}
                      />
                    </div>
                  )}
                  {live && live !== s.label && (
                    <p className="text-sm text-ink-2" aria-live="polite">
                      {live}
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-5 text-[13px] text-ink-3">
        You can close this page. Demux keeps building, and your workspace will
        be ready here.
      </p>
    </section>
  );
}
