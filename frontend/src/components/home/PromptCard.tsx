"use client";

/** The signature prompt card (theme.md §7.2) with example chips (§7.3) and Build. */
import { ArrowRight } from "lucide-react";
import { useId, useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { Button } from "@/components/ui/Button";

const EXAMPLES = ["Unpaid invoices and who I owe", "Job applications by stage"];

export function PromptCard({
  disabled,
  onBuild,
}: {
  disabled: boolean;
  onBuild: (prompt: string) => Promise<boolean>;
}) {
  const id = useId();
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!prompt.trim() || disabled || busy) return;
    setBusy(true);
    const ok = await onBuild(prompt.trim());
    if (!ok) setBusy(false); // on success the page navigates away
  }

  return (
    <form
      onSubmit={submit}
      className="w-full max-w-[760px] rounded-2xl bg-surface px-6 pt-6 pb-[18px] shadow-float"
    >
      <div className="flex gap-4">
        <LogoMark size={46} className="mt-0.5 hidden sm:block" />
        <label htmlFor={id} className="sr-only">
          Describe what you want to keep track of
        </label>
        <textarea
          id={id}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          }}
          rows={3}
          maxLength={4000}
          disabled={disabled}
          placeholder="Describe what you want to keep track of…"
          className="min-h-[96px] w-full resize-none border-0 bg-transparent text-[22px] leading-[1.4] tracking-[-0.01em] text-ink caret-violet outline-none placeholder:text-ink-3 focus:shadow-none focus-visible:shadow-none disabled:opacity-60"
        />
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex min-w-0 flex-1 basis-full flex-wrap gap-2 sm:basis-0">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex}
              disabled={disabled}
              onClick={() => setPrompt(ex)}
              className="h-9 rounded-full border border-chip-line whitespace-nowrap bg-surface-3 px-3.5 text-sm font-medium text-ink-2 transition-[background-color,border-color,color,transform] duration-200 ease-dmx hover:-translate-y-px hover:border-[#DCD2FD] hover:bg-violet-soft hover:text-violet-ink active:translate-y-0 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40"
            >
              {ex}
            </button>
          ))}
        </div>
        <Button
          type="submit"
          loading={busy}
          disabled={disabled || !prompt.trim()}
          className="ml-auto"
        >
          Build{" "}
          <ArrowRight
            size={18}
            strokeWidth={2.2}
            aria-hidden
            className="dmx-nudge"
          />
        </Button>
      </div>
    </form>
  );
}
