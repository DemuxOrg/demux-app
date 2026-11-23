"use client";

/**
 * Details: the prompt, the Gmail searches, the guide, and the run history with cost and
 * tokens per run. This is how to inspect what the agent decided. A white panel that
 * slides in from the right; closes on Escape or a click outside.
 */
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  api,
  type GuideDoc,
  type RunRead,
  type WorkspaceDetail,
} from "@/lib/api";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[13px] font-medium text-ink-3">{title}</h3>
      {children}
    </section>
  );
}

export function DetailsDrawer({
  workspace,
  runs,
  onClose,
}: {
  workspace: WorkspaceDetail;
  runs: RunRead[];
  onClose: () => void;
}) {
  const [guide, setGuide] = useState<GuideDoc | null>(null);
  useEffect(() => {
    api
      .getGuide(workspace.id)
      .then(setGuide)
      .catch(() => setGuide(null));
  }, [workspace.id, workspace.data_version]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const queries = guide?.queries ?? workspace.queries;
  const total = runs.reduce((s, r) => s + r.cost_usd, 0);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgb(12_26_46/0.18)] p-3 backdrop-blur-[2px] animate-[dmx-fade_200ms_var(--ease-dmx)_both]"
      onClick={onClose}
    >
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="details-title"
        className="flex h-full w-full max-w-[640px] animate-[dmx-drawer_320ms_var(--ease-dmx)_both] flex-col overflow-hidden rounded-xl bg-surface shadow-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line-soft py-3 pr-3 pl-6">
          <h2
            id="details-title"
            className="text-lg font-semibold tracking-[-0.015em]"
          >
            Details
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details"
            autoFocus
            className="grid size-11 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink"
          >
            <X size={18} aria-hidden />
          </button>
        </header>
        <div className="flex flex-1 flex-col gap-7 overflow-y-auto px-6 py-6">
          <Section title="Prompt">
            <p className="text-[15px] whitespace-pre-wrap">
              {workspace.prompt}
            </p>
          </Section>
          <Section title="Gmail searches">
            {queries.length ? (
              <ul className="flex flex-wrap gap-2">
                {queries.map((q) => (
                  <li
                    key={q}
                    className="rounded-tag bg-tag px-2 py-1 font-mono text-xs text-ink-2"
                  >
                    {q}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">None yet.</p>
            )}
          </Section>
          <Section title="Guide">
            <pre className="max-h-96 overflow-auto rounded-sm bg-surface-2 p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink-2">
              {guide?.guide || "Empty."}
            </pre>
          </Section>
          <Section title={`Runs · $${total.toFixed(4)} shown`}>
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full text-left text-[13px] tabular">
                <thead className="bg-surface-2 text-ink-3">
                  <tr>
                    <th className="px-3 py-2 font-medium">When</th>
                    <th className="px-3 py-2 font-medium">Kind</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Cost</th>
                    <th className="px-3 py-2 text-right font-medium">
                      Tokens in / out
                    </th>
                    <th className="px-3 py-2 text-right font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr
                      key={r.id}
                      className="border-t border-line-soft align-top"
                    >
                      <td className="px-3 py-2 whitespace-nowrap text-ink-2">
                        {new Date(r.created_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-3 py-2 capitalize">{r.kind}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex h-[22px] items-center rounded-full px-2 text-xs font-medium ${
                            r.status === "done"
                              ? "bg-success-bg text-success"
                              : r.status === "failed"
                                ? "bg-danger-bg text-danger"
                                : "bg-violet-soft text-violet-ink"
                          }`}
                        >
                          {r.status}
                        </span>
                        {(r.summary || r.error) && (
                          <p className="mt-1 max-w-xs text-ink-3">
                            {r.error ?? r.summary}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ${r.cost_usd.toFixed(4)}
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        {r.input_tokens.toLocaleString()} /{" "}
                        {r.output_tokens.toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {r.duration_s != null
                          ? `${Math.round(r.duration_s)}s`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      </aside>
    </div>
  );
}
