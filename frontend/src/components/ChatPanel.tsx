"use client";

/**
 * Chat tab: the user's change requests with each run's reply, and the "Ask for a
 * change" input pinned to the bottom (theme.md §7.4). Wiring is unchanged: a message
 * starts an edit run; the input is disabled while any run is active.
 */
import { ArrowUp } from "lucide-react";
import { useId, useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import type { RunRead, WorkspaceDetail } from "@/lib/api";
import { RunTimeline } from "./RunTimeline";

export function ChatPanel({
  runs,
  workspace,
  onSend,
}: {
  runs: RunRead[];
  workspace: WorkspaceDetail;
  onSend: (text: string) => Promise<void>;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const active = workspace.active_run;
  const edits = runs
    .filter((r) => r.kind === "edit")
    .slice()
    .reverse();
  const locked = !!active || sending;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || locked) return;
    setSending(true);
    try {
      await onSend(text.trim());
      setText("");
    } catch {
      /* not sent: keep the text; the page shows why */
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {!edits.length ? (
          <p className="text-sm text-ink-2">
            Ask for a change in plain words: “add a column for the due date”,
            “group by sender”, “also track refunds”. Undo puts back the version
            before the last change.
          </p>
        ) : (
          <ol className="flex flex-col gap-5">
            {edits.map((r) => (
              <li key={r.id} className="flex flex-col gap-2.5">
                <p className="ml-8 self-end rounded-md bg-surface px-3.5 py-2.5 text-sm text-ink shadow-[0_1px_2px_rgb(22_62_128/0.06)]">
                  {r.input_text}
                </p>
                <div className="mr-4 flex gap-2.5">
                  <LogoMark size={22} className="mt-0.5" />
                  <div className="min-w-0 flex-1 text-sm text-ink-2">
                    {r.status === "done" && (r.summary || "Done.")}
                    {r.status === "failed" && (
                      <span className="text-danger">
                        That didn&apos;t work:{" "}
                        {r.error?.replace(/^[a-z_]+: /, "")} Nothing was
                        changed.
                      </span>
                    )}
                    {(r.status === "queued" || r.status === "running") &&
                      (active?.id === r.id ? (
                        <RunTimeline events={active.events} />
                      ) : (
                        "Working on it…"
                      ))}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <form onSubmit={submit} className="p-3 pt-1">
        <div className="flex items-center gap-2 rounded-lg bg-surface py-1.5 pr-1.5 pl-4 shadow-input transition-shadow duration-150 ease-dmx focus-within:shadow-[0_0_0_3px_rgb(106_61_240/0.22),var(--shadow-input)]">
          <label htmlFor={id} className="sr-only">
            Ask for a change
          </label>
          <input
            id={id}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={locked}
            maxLength={4000}
            placeholder={
              active
                ? "Wait for the current run to finish…"
                : "Ask for a change…"
            }
            className="h-11 min-w-0 flex-1 bg-transparent text-[15px] text-ink caret-violet outline-none placeholder:text-ink-3 focus-visible:shadow-none disabled:opacity-60"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={locked || !text.trim()}
            className="grid size-11 shrink-0 place-items-center rounded-[14px] bg-violet text-white transition-colors duration-150 hover:bg-violet-hover disabled:cursor-not-allowed disabled:bg-sky-200"
          >
            <ArrowUp size={18} strokeWidth={2.4} aria-hidden />
          </button>
        </div>
      </form>
    </div>
  );
}
