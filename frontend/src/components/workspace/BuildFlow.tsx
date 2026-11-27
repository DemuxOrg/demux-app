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
 *
 * Otherwise the card is a small checklist (reading the emails and designing the
 * interface run side by side, so both rows can be working) and one thinking line.
 *
 * Cancel (every step) asks first, inline; `onCancel` stops the build (theme.md §7.10).
 */
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { LogoMark } from "@/components/brand/Logo";
import { RevealText } from "@/components/motion/Reveal";
import { Button } from "@/components/ui/Button";
import { Checklist, ThinkingLine } from "@/components/build/BuildParts";
import {
  designerTrack,
  latestEvent,
  readingProgress,
  readingTrack,
} from "@/components/build/model";
import {
  api,
  ApiError,
  handleAuthError,
  type ActiveRun,
  type SetupQuestion,
} from "@/lib/api";

type Answer = { choice: number; other: string };

export function BuildFlow({
  workspaceId,
  prompt,
  run,
  onChanged,
  onCancel,
}: {
  workspaceId: string;
  prompt: string;
  run: ActiveRun | null;
  onChanged: () => Promise<void> | void;
  /** Stop the build: deletes the workspace and goes back to Create. */
  onCancel: () => Promise<void>;
}) {
  const setup = run?.setup ?? null;
  const events = run?.events ?? [];
  // The user's answers went out, ahead of the next poll.
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const designDone = events.some(
    (e) => e.phase === "process" || e.phase === "app",
  );
  const qState = setup?.questions_state ?? (designDone ? "none" : "deciding");
  const asking = qState === "asking" && !!setup?.questions.length;

  const questionsDone =
    sent ||
    !!setup?.answered ||
    ["none", "answered", "timed_out"].includes(qState);

  const progress = readingProgress(events);
  const reading = readingTrack(events, progress);
  const designer = designerTrack(events);

  const step = !questionsDone ? 1 : reading !== "done" ? 2 : 3;
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
    <section className="w-full rounded-[24px] bg-surface px-6 pt-7 pb-6 shadow-float sm:px-7">
      <div key={`${step}:${asking}`} className="animate-dmx-rise">
        <div className="flex items-center gap-3">
          <LogoMark size={28} className="animate-dmx-breathe" />
          <RevealText
            as="h1"
            text={title}
            className="min-w-0 flex-1 text-xl leading-[1.2] font-semibold tracking-[-0.015em]"
          />
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-expanded={confirming}
            className="-mr-2 h-11 shrink-0 rounded-full px-2 text-[13px] font-medium text-ink-3 transition-colors hover:text-danger"
          >
            Cancel
          </button>
        </div>
        <p className="mt-1.5 truncate text-sm text-ink-3" title={prompt}>
          “{prompt}”
        </p>
        {timedOut && step > 1 && (
          <p className="mt-1.5 text-[13px] text-ink-3">
            We went ahead with the recommended answers.
          </p>
        )}
      </div>

      <div className="mt-5">
        {step === 1 && asking && setup ? (
          <QuestionsStep
            questions={setup.questions}
            busy={busy}
            onContinue={send}
          />
        ) : (
          <>
            <Checklist
              step={step}
              rows={[
                { state: questionsDone ? "done" : "working", detail: "" },
                {
                  state: step === 1 ? "waiting" : reading,
                  detail:
                    progress && reading !== "waiting"
                      ? `${reading === "done" ? progress.total : progress.done} of ${progress.total}`
                      : "",
                },
                {
                  state: step === 1 ? "waiting" : designer.state,
                  detail: designer.label,
                },
              ]}
            />
            <ThinkingLine
              phase={
                step === 1 ? "request" : step === 2 ? "reading" : "designing"
              }
              fact={latestEvent(events)}
            />
          </>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      )}
      {step >= 2 && !confirming && (
        <p className="mt-5 text-[13px] text-ink-3">
          That&apos;s everything we need from you. You can close this page; your
          workspace will be ready here.
        </p>
      )}
      {confirming && (
        <CancelStrip onKeep={() => setConfirming(false)} onStop={onCancel} />
      )}
    </section>
  );
}

/** "Stop this build?", inline (theme.md §7.10). */
function CancelStrip({
  onKeep,
  onStop,
}: {
  onKeep: () => void;
  onStop: () => Promise<void>;
}) {
  const [stopping, setStopping] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onKeep();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onKeep]);

  async function stop() {
    setStopping(true);
    setFailed(false);
    try {
      await onStop();
    } catch {
      setFailed(true);
      setStopping(false);
    }
  }

  return (
    <div
      role="alertdialog"
      aria-labelledby="cancel-build"
      className="mt-5 flex animate-dmx-rise flex-wrap items-center gap-x-3 gap-y-2 rounded-sm bg-danger-bg px-4 py-3"
    >
      <p
        id="cancel-build"
        className="min-w-0 flex-1 basis-60 text-sm text-danger"
      >
        {failed
          ? "Couldn't stop the build. Try again."
          : "Stop this build? The workspace is removed and your prompt goes back in the box."}
      </p>
      <div className="ml-auto flex items-center gap-1">
        <Button variant="quiet" size="sm" onClick={onKeep} autoFocus>
          Keep building
        </Button>
        <button
          type="button"
          onClick={stop}
          disabled={stopping}
          className="inline-flex h-11 items-center gap-2 rounded-full px-3 text-sm font-medium text-danger hover:underline disabled:opacity-70"
        >
          {stopping && <Spinner size={16} />}
          Stop build
        </button>
      </div>
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
