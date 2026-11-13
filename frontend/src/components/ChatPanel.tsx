"use client";

/**
 * Chat tab: the user's edit messages with each run's summary, live events of the
 * active edit, and a text box (disabled while any run is active).
 */
import { useState } from "react";
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
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const active = workspace.active_run;
  const edits = runs.filter((r) => r.kind === "edit").slice().reverse();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      await onSend(text.trim());
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {!edits.length && (
          <p className="text-sm text-gray-500">
            Ask for a change: “add a column for the due date”, “group by
            sender”, “also track refunds”. Undo reverts the last change.
          </p>
        )}
        {edits.map((r) => (
          <div key={r.id} className="space-y-2">
            <div className="ml-8 rounded-lg bg-gray-900 px-3 py-2 text-sm text-white">
              {r.input_text}
            </div>
            <div className="mr-8 rounded-lg bg-gray-100 px-3 py-2 text-sm">
              {r.status === "done" && (r.summary || "Done.")}
              {r.status === "failed" && (
                <span className="text-red-700">
                  That didn’t work: {r.error?.replace(/^[a-z_]+: /, "")} Nothing
                  was changed.
                </span>
              )}
              {(r.status === "queued" || r.status === "running") &&
                (active?.id === r.id ? (
                  <RunTimeline events={active.events} compact />
                ) : (
                  "Working…"
                ))}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="border-t border-gray-200 p-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
          disabled={!!active || sending}
          rows={3}
          placeholder={active ? "Wait for the current run to finish…" : "Ask for a change"}
          className="w-full resize-none rounded border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50"
        />
        <div className="mt-2 flex justify-end">
          <button
            type="submit"
            disabled={!!active || sending || !text.trim()}
            className="rounded bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
