"use client";

/**
 * Build flow card (theme.md §7.10): five steps from Build to a ready workspace.
 *
 *   1 Your look · 2 A few questions · 3 Your layout · 4 Reading your emails · 5 Building
 *
 * Steps 1-3 are the user's turn and run while Demux already works in the background
 * (the design agent asks questions after its first searches and proposes layouts from
 * the guide; see docs/UI_GENERATION_PLAN.md §3). The total is always five: a step that
 * is not needed ticks off. Answers go to POST /workspaces/{id}/setup; the build waits
 * for them (2 minutes at most, then uses the preselected answers).
 */
import { ArrowRight, Check } from "lucide-react";
import { useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { RevealText } from "@/components/motion/Reveal";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { LayoutThumb } from "@/components/workspace/LayoutThumb";
import { PaletteTiles } from "@/components/workspace/PaletteTiles";
import {
  api,
  ApiError,
  handleAuthError,
  type ActiveRun,
  type PaletteId,
  type PaletteInfo,
  type SetupQuestion,
} from "@/lib/api";

const STEPS = [
  "Your look",
  "A few questions",
  "Your layout",
  "Reading your emails",
  "Building your workspace",
] as const;

const TITLES = [
  "How should your workspace look?",
  "A few questions",
  "What should your workspace show?",
  "Reading your emails",
  "Almost there",
] as const;

type Answer = { choice: number; other: string };

function plural(n: number, noun: string): string {
  const word = noun.replace(/_/g, " ");
  return `${n} ${n === 1 || word.endsWith("s") ? word : `${word}s`}`;
}

export function BuildFlow({
  workspaceId,
  prompt,
  run,
  palettes,
  palette,
  recordCounts,
  onChanged,
}: {
  workspaceId: string;
  prompt: string;
  run: ActiveRun | null;
  palettes: PaletteInfo[];
  palette: PaletteId;
  recordCounts: Record<string, number>;
  onChanged: () => Promise<void> | void;
}) {
  const setup = run?.setup ?? null;
  const events = run?.events ?? [];
  // The user's own progress, ahead of the next poll.
  const [sent, setSent] = useState({
    look: false,
    answers: false,
    layout: false,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const designDone = events.some(
    (e) => e.phase === "process" || e.phase === "app",
  );
  const qState = setup?.questions_state ?? (designDone ? "none" : "deciding");
  const lState = setup?.layout_state ?? (designDone ? "none" : "waiting");

  const lookDone = sent.look || !!setup?.palette;
  const questionsDone =
    sent.answers ||
    !!setup?.answered ||
    ["none", "answered", "timed_out"].includes(qState);
  const layoutDone =
    sent.layout ||
    !!setup?.layout_chosen ||
    ["chosen", "timed_out", "auto", "none"].includes(lState);

  let progress: { done: number; total: number } | null = null;
  for (let i = events.length - 1; i >= 0 && !progress; i--) {
    const e = events[i];
    if (e.phase === "process" && e.total != null && e.done != null)
      progress = { done: e.done, total: e.total };
  }
  const readingDone =
    !!progress && progress.total > 0 && progress.done >= progress.total;

  const step = !lookDone
    ? 1
    : !questionsDone
      ? 2
      : !layoutDone
        ? 3
        : !readingDone
          ? 4
          : 5;
  const timedOut =
    (qState === "timed_out" && !sent.answers && !setup?.answered) ||
    (lState === "timed_out" && !sent.layout && !setup?.layout_chosen);

  async function send(
    body: Parameters<typeof api.updateSetup>[1],
    mark: keyof typeof sent,
  ) {
    setBusy(true);
    setError(null);
    try {
      await api.updateSetup(workspaceId, body);
      setSent((s) => ({ ...s, [mark]: true }));
      await onChanged();
    } catch (e) {
      if (handleAuthError(e)) return;
      // 409: the build already moved on (it used the recommended answer).
      if (e instanceof ApiError && e.status === 409) {
        setSent((s) => ({ ...s, [mark]: true }));
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
          Step {step} of 5 · {STEPS[step - 1]}
        </p>
      </div>

      <StepBar step={step} progress={progress} />

      <div key={step} className="animate-dmx-rise">
        <RevealText
          as="h1"
          text={TITLES[step - 1]}
          className="mt-6 text-[28px] leading-[1.12] font-medium tracking-[-0.03em] sm:text-[30px]"
        />
        <p className="mt-2 truncate text-sm text-ink-3" title={prompt}>
          “{prompt}”
        </p>
        {timedOut && step > 2 && (
          <p className="mt-2 text-[13px] text-ink-3">
            We went ahead with the recommended answers.
          </p>
        )}

        <div className="mt-6">
          {step === 1 && (
            <LookStep
              palettes={palettes}
              initial={setup?.palette ?? palette}
              busy={busy}
              onContinue={(p) => send({ palette: p }, "look")}
            />
          )}
          {step === 2 &&
            (qState === "asking" && setup?.questions.length ? (
              <QuestionsStep
                questions={setup.questions}
                busy={busy}
                onContinue={(answers) => send({ answers }, "answers")}
              />
            ) : (
              <Waiting label="Looking at your emails" />
            ))}
          {step === 3 &&
            (lState === "choosing" && setup?.layout_options.length ? (
              <LayoutStep
                options={setup.layout_options}
                primary={setup.layout_primary}
                palette={
                  palettes.find((p) => p.id === (setup.palette ?? palette)) ??
                  palettes[0]
                }
                busy={busy}
                onContinue={(layout) => send({ layout }, "layout")}
              />
            ) : (
              <Waiting label="Preparing options from your emails" />
            ))}
          {step === 4 && (
            <ReadingStep progress={progress} recordCounts={recordCounts} />
          )}
          {step === 5 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-base font-medium text-ink">
                Building your workspace
              </p>
              <p className="text-sm text-ink-2" aria-live="polite">
                {[...events].reverse().find((e) => e.phase === "app")?.label ??
                  "Putting your layouts together"}
              </p>
            </div>
          )}
        </div>

        {error && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        )}
        {step >= 4 && (
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
      aria-valuemax={5}
      aria-valuenow={step}
      aria-valuetext={`Step ${step} of 5: ${STEPS[step - 1]}`}
      className="mt-5 grid grid-cols-5 gap-1"
    >
      {STEPS.map((s, i) => {
        const n = i + 1;
        const demux = n >= 4;
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
                  style={{ width: n === 4 ? `${pct}%` : "100%" }}
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

/* ------------------------------------------------------------------ 1 · look */

function LookStep({
  palettes,
  initial,
  busy,
  onContinue,
}: {
  palettes: PaletteInfo[];
  initial: PaletteId;
  busy: boolean;
  onContinue: (p: PaletteId) => void;
}) {
  const [value, setValue] = useState<PaletteId>(initial);
  if (!palettes.length) return <Waiting label="Loading the looks" />;
  return (
    <>
      <PaletteTiles
        palettes={palettes}
        value={value}
        onChange={setValue}
        label="Look"
        className="grid grid-cols-2 gap-2.5 min-[420px]:grid-cols-3 sm:grid-cols-5"
      />
      <Footer
        note="This sets the colours of your workspace."
        busy={busy}
        onClick={() => onContinue(value)}
      />
    </>
  );
}

/* ------------------------------------------------------------------ 2 · questions */

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
      <Footer busy={busy} onClick={submit} />
    </>
  );
}

/* ------------------------------------------------------------------ 3 · layout */

function LayoutStep({
  options,
  primary,
  palette,
  busy,
  onContinue,
}: {
  options: {
    id: string;
    block: string;
    title: string;
    description: string;
    recommended: boolean;
  }[];
  primary: string | null;
  palette: PaletteInfo | undefined;
  busy: boolean;
  onContinue: (layout: { views: string[]; primary: string }) => void;
}) {
  const [chosen, setChosen] = useState<string[]>(() => {
    const rec = options.filter((o) => o.recommended).map((o) => o.id);
    return rec.length ? rec : [options[0].id];
  });
  const [first, setFirst] = useState<string>(primary ?? options[0].id);
  const opensFirst = chosen.includes(first) ? first : chosen[0];

  function toggle(id: string) {
    setChosen((c) =>
      c.includes(id)
        ? c.length === 1
          ? c
          : c.filter((x) => x !== id)
        : [...c, id],
    );
  }

  return (
    <>
      <fieldset className="m-0 border-0 p-0">
        <legend className="sr-only">Layouts</legend>
        <div className="grid grid-cols-1 gap-2.5 min-[520px]:grid-cols-2">
          {options.map((o) => {
            const selected = chosen.includes(o.id);
            return (
              <label
                key={o.id}
                className={`relative flex cursor-pointer flex-col gap-2.5 rounded-md bg-surface transition-[translate,box-shadow,border-color] duration-[250ms] ease-dmx hover:-translate-y-0.5 hover:shadow-glass has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-violet/25 ${
                  selected
                    ? "border-2 border-violet p-[11px]"
                    : "border border-line p-3"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => toggle(o.id)}
                  className="sr-only"
                />
                <LayoutThumb block={o.block} palette={palette} />
                <span className="flex items-start gap-2">
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-ink">
                      {o.title}
                    </span>
                    {o.description && (
                      <span className="mt-0.5 block text-[13px] text-ink-3">
                        {o.description}
                      </span>
                    )}
                  </span>
                  <span
                    aria-hidden
                    className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-[6px] border ${
                      selected
                        ? "border-violet bg-violet text-white"
                        : "border-pending-line"
                    }`}
                  >
                    {selected && <Check size={13} strokeWidth={3} />}
                  </span>
                </span>
                {o.recommended && (
                  <span className="absolute top-2 left-2 rounded-tag bg-surface/90 px-[7px] py-[3px] text-xs text-ink-2">
                    Recommended
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </fieldset>
      {chosen.length === 1 && options.length > 1 && (
        <p className="mt-2 text-[13px] text-ink-3">Pick at least one.</p>
      )}
      {chosen.length > 1 && (
        <label className="mt-4 flex flex-wrap items-center gap-2.5">
          <span className="text-[13px] font-medium text-ink-2">
            Opens first
          </span>
          <select
            value={opensFirst}
            onChange={(e) => setFirst(e.target.value)}
            className="h-10 cursor-pointer rounded-full border border-line bg-surface px-3.5 text-sm text-ink-2 outline-none focus:border-violet-line focus:ring-[3px] focus:ring-violet/25"
          >
            {options
              .filter((o) => chosen.includes(o.id))
              .map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title}
                </option>
              ))}
          </select>
        </label>
      )}
      <Footer
        busy={busy}
        onClick={() =>
          onContinue({
            views: options
              .filter((o) => chosen.includes(o.id))
              .map((o) => o.id),
            primary: opensFirst,
          })
        }
      />
    </>
  );
}

/* ------------------------------------------------------------------ 4 · reading */

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
