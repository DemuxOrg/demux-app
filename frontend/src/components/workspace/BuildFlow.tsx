"use client";

/**
 * Build flow card (theme.md §7.10): three steps from Build to a ready workspace.
 *
 *   1 Your request · 2 Reading your emails · 3 Building your workspace
 *
 * Step 1 is the user's turn only when the design agent finds gaps in the request: after
 * its first searches it asks one multiple-choice question per gap (none for a precise
 * request, up to five for a vague one). Without questions the step ticks off on its own.
 * The total is always three. Answers go to POST /workspaces/{id}/setup; the build waits
 * for them (2 minutes at most, then uses the preselected answers).
 */
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { RevealText } from "@/components/motion/Reveal";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import {
  api,
  ApiError,
  handleAuthError,
  type ActiveRun,
  type SetupQuestion,
} from "@/lib/api";

const STEPS = [
  "Your request",
  "Reading your emails",
  "Building your workspace",
] as const;
const TOTAL = STEPS.length;

type Answer = { choice: number; other: string };

function plural(n: number, noun: string): string {
  const word = noun.replace(/_/g, " ");
  return `${n} ${n === 1 || word.endsWith("s") ? word : `${word}s`}`;
}

export function BuildFlow({
  workspaceId,
  prompt,
  run,
  recordCounts,
  onChanged,
}: {
  workspaceId: string;
  prompt: string;
  run: ActiveRun | null;
  recordCounts: Record<string, number>;
  onChanged: () => Promise<void> | void;
}) {
  const setup = run?.setup ?? null;
  const events = run?.events ?? [];
  // The user's answers went out, ahead of the next poll.
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const designDone = events.some(
    (e) => e.phase === "process" || e.phase === "app",
  );
  const qState = setup?.questions_state ?? (designDone ? "none" : "deciding");
  const asking = qState === "asking" && !!setup?.questions.length;

  const questionsDone =
    sent ||
    !!setup?.answered ||
    ["none", "answered", "timed_out"].includes(qState);

  let progress: { done: number; total: number } | null = null;
  for (let i = events.length - 1; i >= 0 && !progress; i--) {
    const e = events[i];
    if (e.phase === "process" && e.total != null && e.done != null)
      progress = { done: e.done, total: e.total };
  }
  const readingDone =
    !!progress && progress.total > 0 && progress.done >= progress.total;

  const step = !questionsDone ? 1 : !readingDone ? 2 : 3;
  const title =
    step === 1
      ? asking
        ? "A few questions"
        : "Understanding your request"
      : step === 2
        ? "Reading your emails"
        : "Almost there";
  const timedOut = qState === "timed_out" && !sent && !setup?.answered;

  async function send(answers: Record<string, string>) {
    setBusy(true);
    setError(null);
    try {
      await api.updateSetup(workspaceId, { answers });
      setSent(true);
      await onChanged();
    } catch (e) {
      if (handleAuthError(e)) return;
      // 409: the build already moved on (it used the recommended answers).
      if (e instanceof ApiError && e.status === 409) {
        setSent(true);
        await onChanged();
      } else
        setError(
          e instanceof ApiError ? e.message : "Couldn't save that. Try again.",
        );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full rounded-2xl bg-surface px-6 pt-7 pb-6 shadow-float sm:px-9 sm:pt-8">
      <div className="flex items-center justify-between gap-3">
        <LogoMark size={40} className="animate-dmx-breathe" />
        <p className="text-[13px] font-medium text-ink-3 tabular">
          Step {step} of {TOTAL} · {STEPS[step - 1]}
        </p>
      </div>

      <StepBar step={step} progress={progress} />

      <div key={`${step}:${asking}`} className="animate-dmx-rise">
        <RevealText
          as="h1"
          text={title}
          className="mt-6 text-[28px] leading-[1.12] font-medium tracking-[-0.03em] sm:text-[30px]"
        />
        <p className="mt-2 truncate text-sm text-ink-3" title={prompt}>
          “{prompt}”
        </p>
        {timedOut && step > 1 && (
          <p className="mt-2 text-[13px] text-ink-3">
            We went ahead with the recommended answers.
          </p>
        )}

        <div className="mt-6">
          {step === 1 &&
            (asking && setup ? (
              <QuestionsStep
                questions={setup.questions}
                busy={busy}
                onContinue={send}
              />
            ) : (
              <Waiting label="Looking at your emails" />
            ))}
          {step === 2 && (
            <ReadingStep progress={progress} recordCounts={recordCounts} />
          )}
          {step === 3 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-base font-medium text-ink">
                Building your workspace
              </p>
              <p className="text-sm text-ink-2" aria-live="polite">
                {[...events].reverse().find((e) => e.phase === "app")?.label ??
                  "Putting your workspace together"}
              </p>
            </div>
          )}
        </div>

        {error && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        )}
        {step >= 2 && (
          <p className="mt-6 text-[13px] text-ink-3">
            That&apos;s everything we need from you. You can close this page;
            your workspace will be ready here.
          </p>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ step bar */

function StepBar({
  step,
  progress,
}: {
  step: number;
  progress: { done: number; total: number } | null;
}) {
  const pct = progress?.total
    ? Math.max(6, Math.round((progress.done / progress.total) * 100))
    : 6;
  return (
    <div
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={TOTAL}
      aria-valuenow={step}
      aria-valuetext={`Step ${step} of ${TOTAL}: ${STEPS[step - 1]}`}
      className="mt-5 grid grid-cols-3 gap-1"
    >
      {STEPS.map((s, i) => {
        const n = i + 1;
        const demux = n >= 2;
        return (
          <span
            key={s}
            aria-hidden
            className="h-1.5 overflow-hidden rounded-full bg-track"
          >
            {n < step ? (
              <span className="block h-full w-full rounded-full bg-violet" />
            ) : n === step ? (
              demux ? (
                <span
                  className="block h-full animate-dmx-flow rounded-full bg-brand-flow transition-[width] duration-500 ease-dmx"
                  style={{ width: n === 2 ? `${pct}%` : "100%" }}
                />
              ) : (
                <span className="block h-full w-full rounded-full bg-violet-line" />
              )
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

function Waiting({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-2" aria-live="polite">
      <Spinner size={22} />
      <p className="text-[15px] font-medium text-ink-2">{label}</p>
    </div>
  );
}

function Footer({
  note,
  busy,
  disabled,
  onClick,
}: {
  note?: string;
  busy: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
      <p className="text-[13px] text-ink-3">{note}</p>
      <Button size="sm" onClick={onClick} loading={busy} disabled={disabled}>
        Continue <ArrowRight size={18} aria-hidden className="dmx-nudge" />
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ 1 · questions */

function QuestionsStep({
  questions,
  busy,
  onContinue,
}: {
  questions: SetupQuestion[];
  busy: boolean;
  onContinue: (answers: Record<string, string>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, Answer>>(() =>
    Object.fromEntries(
      questions.map((q) => [q.id, { choice: q.recommended, other: "" }]),
    ),
  );
  const OTHER = -1;

  function submit() {
    const out: Record<string, string> = {};
    for (const q of questions) {
      const a = answers[q.id];
      out[q.id] =
        a.choice === OTHER && a.other.trim()
          ? `Other: ${a.other.trim()}`
          : (q.options[a.choice] ?? q.options[q.recommended]);
    }
    onContinue(out);
  }

  return (
    <>
      <div className="flex flex-col gap-6">
        {questions.map((q) => {
          const a = answers[q.id];
          const set = (patch: Partial<Answer>) =>
            setAnswers((s) => ({ ...s, [q.id]: { ...s[q.id], ...patch } }));
          return (
            <fieldset
              key={q.id}
              className="m-0 flex flex-col gap-2 border-0 p-0"
            >
              <legend className="mb-2 text-base font-semibold text-ink">
                {q.question}
              </legend>
              {[...q.options, null].map((opt, i) => {
                const idx = opt === null ? OTHER : i;
                const selected = a.choice === idx;
                return (
                  <label
                    key={idx}
                    className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-sm border px-3.5 py-2 text-[15px] font-medium transition-colors duration-150 has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-violet/25 ${
                      selected
                        ? "border-violet-line bg-violet-soft text-violet-ink"
                        : "border-line text-ink-2 hover:bg-surface-2"
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      checked={selected}
                      onChange={() => set({ choice: idx })}
                      className="size-[18px] accent-violet"
                    />
                    <span className="min-w-0 flex-1">{opt ?? "Other…"}</span>
                    {idx === q.recommended && (
                      <span className="rounded-tag bg-tag px-[7px] py-[3px] text-xs font-normal text-ink-2">
                        Recommended
                      </span>
                    )}
                  </label>
                );
              })}
              {a.choice === OTHER && (
                <input
                  aria-label={`Your answer: ${q.question}`}
                  autoFocus
                  value={a.other}
                  maxLength={280}
                  onChange={(e) => set({ other: e.target.value })}
                  placeholder="Type your answer"
                  className="h-10 rounded-sm border border-line px-3.5 text-[15px] text-ink caret-violet outline-none placeholder:text-ink-3 focus:border-violet-line focus:ring-[3px] focus:ring-violet/25"
                />
              )}
            </fieldset>
          );
        })}
      </div>
      <Footer
        note="We picked our best guess for each. Change what doesn't fit."
        busy={busy}
        onClick={submit}
      />
    </>
  );
}

/* ------------------------------------------------------------------ 2 · reading */

function ReadingStep({
  progress,
  recordCounts,
}: {
  progress: { done: number; total: number } | null;
  recordCounts: Record<string, number>;
}) {
  const main = Object.entries(recordCounts)
    .filter(([t]) => !t.startsWith("_"))
    .sort((a, b) => b[1] - a[1])[0];
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-base font-medium text-ink tabular">
        {progress
          ? `${progress.done} of ${plural(progress.total, "thread")} read`
          : "Collecting matching emails"}
      </p>
      <p className="text-sm text-ink-2" aria-live="polite">
        {main
          ? `${plural(main[1], main[0])} found so far`
          : "Looking for the first records"}
      </p>
    </div>
  );
}
