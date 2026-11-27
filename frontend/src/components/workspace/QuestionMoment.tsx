"use client";

/**
 * Question moments (theme.md §7.15): when the build needs an answer, the screen dims and
 * Demux asks one question at a time; the live build stays visible underneath.
 *
 * `moments` is the queue still waiting (the look, then each clarifying question, in
 * order). The first one shows; `onAnswer` sends it (one answer per request) and the
 * parent drops it from the queue. Between two moments the scrim stays: the content fades
 * out (200 ms), and the next starts 300 ms later. After the last, the scrim fades out.
 *
 * Loaded with next/dynamic: a clear prompt never downloads it.
 */
import { ArrowRight } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { LogoMark } from "@/components/brand/Logo";
import { Button } from "@/components/ui/Button";
import type { Moment } from "@/components/build/model";

const TYPE_MS = 18;
const TYPE_MAX_MS = 1200;
const OUT_MS = 200;
const GAP_MS = 300;

const REDUCED = "(prefers-reduced-motion: reduce)";
function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (cb) => {
      const q = window.matchMedia(REDUCED);
      q.addEventListener("change", cb);
      return () => q.removeEventListener("change", cb);
    },
    () => window.matchMedia(REDUCED).matches,
    () => false,
  );
}

export default function QuestionMoments({
  moments,
  onAnswer,
}: {
  moments: Moment[];
  onAnswer: (moment: Moment, value: string) => Promise<void>;
}) {
  const reduced = useReducedMotion();
  // The moment on screen; it stays while it fades out, then the gap, then the next.
  const [shown, setShown] = useState<Moment | null>(moments[0] ?? null);
  const [leaving, setLeaving] = useState(false);
  const next = moments[0] ?? null;

  // A new head of the queue while nothing is on screen: show it (after the gap).
  const idle = !shown && !leaving;
  useEffect(() => {
    if (!idle || !next) return;
    const t = setTimeout(() => setShown(next), reduced ? 0 : GAP_MS);
    return () => clearTimeout(t);
  }, [idle, next, reduced]);

  // The moment closed on its own (timed out, or answered in another tab).
  if (shown && !leaving && !moments.some((m) => m.key === shown.key)) {
    setLeaving(true);
  }
  useEffect(() => {
    if (!leaving) return;
    const t = setTimeout(
      () => {
        setShown(null);
        setLeaving(false);
      },
      reduced ? 0 : OUT_MS,
    );
    return () => clearTimeout(t);
  }, [leaving, reduced]);

  const answer = useCallback(
    async (m: Moment, value: string) => {
      setLeaving(true);
      await onAnswer(m, value);
    },
    [onAnswer],
  );

  if (!shown && !next) return null;
  return (
    <div
      className="fixed inset-0 z-50 grid animate-dmx-dim place-items-center overflow-y-auto bg-[rgb(12_26_46/0.78)] px-4 py-10"
      // Clicks on the scrim do nothing: the question needs an answer (or Esc).
    >
      {shown && (
        <MomentContent
          key={shown.key}
          moment={shown}
          leaving={leaving}
          reduced={reduced}
          onAnswer={answer}
        />
      )}
    </div>
  );
}

function MomentContent({
  moment,
  leaving,
  reduced,
  onAnswer,
}: {
  moment: Moment;
  leaving: boolean;
  reduced: boolean;
  onAnswer: (m: Moment, value: string) => void;
}) {
  const OTHER = moment.options.length;
  const [choice, setChoice] = useState(moment.recommended);
  const [other, setOther] = useState("");
  const [typed, setTyped] = useState(reduced ? moment.question.length : 0);
  const typing = typed < moment.question.length;
  const box = useRef<HTMLDivElement>(null);
  const labelId = `moment-${moment.key}`;

  // The dialog takes focus at once, so any key can finish the typing.
  useEffect(() => {
    box.current?.focus({ preventScroll: true });
  }, []);

  // Type the question out (§9 `type`), at most 1.2 s whatever its length.
  useEffect(() => {
    if (!typing) return;
    const perTick = Math.max(
      1,
      Math.ceil(moment.question.length / (TYPE_MAX_MS / TYPE_MS)),
    );
    const t = setInterval(
      () => setTyped((n) => Math.min(moment.question.length, n + perTick)),
      TYPE_MS,
    );
    return () => clearInterval(t);
  }, [typing, moment.question.length]);

  // Once the options are there, focus the preselected one.
  useEffect(() => {
    if (typing) return;
    box.current
      ?.querySelector<HTMLInputElement>(`input[value="${moment.recommended}"]`)
      ?.focus();
  }, [typing, moment.recommended]);

  function value(): string {
    if (choice === OTHER) {
      const text = other.trim();
      if (!text) return moment.options[moment.recommended];
      return moment.kind === "look" ? text : `Other: ${text}`;
    }
    return moment.options[choice];
  }
  const submit = () => {
    if (!leaving) onAnswer(moment, value());
  };

  function onKeyDown(e: React.KeyboardEvent) {
    if (typing) {
      e.preventDefault();
      setTyped(moment.question.length);
      return;
    }
    const inText =
      (e.target as HTMLElement).tagName === "INPUT" &&
      (e.target as HTMLInputElement).type === "text";
    if (e.key === "Enter" || e.key === "Escape") {
      e.preventDefault();
      submit();
    } else if (!inText && /^[1-9]$/.test(e.key)) {
      const n = Number(e.key) - 1;
      if (n <= OTHER) {
        e.preventDefault();
        setChoice(n);
      }
    } else if (e.key === "Tab") {
      // Keep focus inside the moment.
      const items = Array.from(
        box.current?.querySelectorAll<HTMLElement>(
          'input:not([type="radio"]), input[type="radio"]:checked, button',
        ) ?? [],
      );
      if (!items.length) return;
      const i = items.indexOf(document.activeElement as HTMLElement);
      const to = e.shiftKey
        ? items[(i - 1 + items.length) % items.length]
        : items[(i + 1) % items.length];
      e.preventDefault();
      to.focus();
    }
  }

  return (
    <div
      ref={box}
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelId}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      onPointerDown={() => typing && setTyped(moment.question.length)}
      className={`w-full max-w-[600px] outline-none transition-opacity duration-200 ${leaving ? "opacity-0" : ""}`}
    >
      <LogoMark size={56} className="animate-dmx-speak" />
      <h2 id={labelId} className="sr-only">
        {moment.question}
      </h2>
      <p
        aria-hidden
        className="mt-6 min-h-[1.3em] text-[19px] leading-[1.3] font-medium tracking-[-0.01em] text-white sm:text-2xl"
      >
        {moment.question.slice(0, typed)}
      </p>

      {!typing && (
        <div className="animate-dmx-options">
          <fieldset className="m-0 mt-5 flex flex-col gap-2 border-0 p-0">
            <legend className="sr-only">{moment.question}</legend>
            {[...moment.options, null].map((opt, i) => {
              const selected = choice === i;
              return (
                <label
                  key={i}
                  className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-sm border px-3.5 py-2 text-[15px] font-medium transition-colors duration-150 has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-white/40 ${
                    selected
                      ? "border-white bg-white text-ink"
                      : "border-white/[.18] bg-white/10 text-white hover:bg-white/[.16]"
                  }`}
                >
                  <input
                    type="radio"
                    name={labelId}
                    value={i}
                    checked={selected}
                    onChange={() => setChoice(i)}
                    className="size-[18px] accent-violet"
                  />
                  <span className="min-w-0 flex-1">{opt ?? "Other…"}</span>
                  {i === moment.recommended && (
                    <span
                      className={`rounded-tag px-[7px] py-[3px] text-xs font-normal ${
                        selected
                          ? "bg-tag text-ink-2"
                          : "bg-white/[.16] text-white"
                      }`}
                    >
                      Recommended
                    </span>
                  )}
                </label>
              );
            })}
            {choice === OTHER && (
              <input
                aria-label={`Your answer: ${moment.question}`}
                autoFocus
                value={other}
                maxLength={280}
                onChange={(e) => setOther(e.target.value)}
                placeholder={
                  moment.kind === "look"
                    ? "Describe it, e.g. navy and gold, serif headings"
                    : "Type your answer"
                }
                className="h-11 rounded-sm bg-white px-3.5 text-[15px] text-ink caret-violet outline-none placeholder:text-ink-3 focus:ring-[3px] focus:ring-white/40"
              />
            )}
          </fieldset>
          <div className="mt-5 flex justify-end">
            <Button size="sm" onClick={submit} disabled={leaving}>
              Continue{" "}
              <ArrowRight size={18} aria-hidden className="dmx-nudge" />
            </Button>
          </div>
          <p className="mt-3 text-right text-[13px] text-white/70">
            If you don&apos;t answer, Demux goes with the recommended option.
          </p>
        </div>
      )}
    </div>
  );
}
