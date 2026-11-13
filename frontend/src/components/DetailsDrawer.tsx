"use client";

/**
 * Details drawer: the prompt, the guide, the queries, and the run history with cost and
 * tokens per run. This is how to inspect what the agent decided.
 */
import { useEffect, useState } from "react";
import { api, type GuideDoc, type RunRead, type WorkspaceDetail } from "@/lib/api";

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
    api.getGuide(workspace.id).then(setGuide).catch(() => setGuide(null));
  }, [workspace.id, workspace.data_version]);

  const total = runs.reduce((s, r) => s + r.cost_usd, 0);
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/20" onClick={onClose}>
      <aside
        className="h-full w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Details</h2>
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-900">
            Close ✕
          </button>
        </div>
        <section className="mb-6">
          <h3 className="mb-1 text-sm font-medium text-gray-500">Prompt</h3>
          <p className="text-sm whitespace-pre-wrap">{workspace.prompt}</p>
        </section>
        <section className="mb-6">
          <h3 className="mb-1 text-sm font-medium text-gray-500">Gmail searches</h3>
          {(guide?.queries ?? workspace.queries).length ? (
            <ul className="space-y-1">
              {(guide?.queries ?? workspace.queries).map((q) => (
                <li key={q} className="rounded bg-gray-100 px-2 py-1 font-mono text-xs">
                  {q}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">None yet.</p>
          )}
        </section>
        <section className="mb-6">
          <h3 className="mb-1 text-sm font-medium text-gray-500">Guide</h3>
          <pre className="max-h-96 overflow-auto rounded bg-gray-50 p-3 text-xs whitespace-pre-wrap">
            {guide?.guide || "(empty)"}
          </pre>
        </section>
        <section>
          <h3 className="mb-1 text-sm font-medium text-gray-500">
            Runs · ${total.toFixed(4)} shown
          </h3>
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                <th className="py-1">When</th>
                <th>Kind</th>
                <th>Status</th>
                <th className="text-right">Cost</th>
                <th className="text-right">Tokens in/out</th>
                <th className="text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-gray-100 align-top">
                  <td className="py-1 whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td>{r.kind}</td>
                  <td>
                    {r.status}
                    {(r.summary || r.error) && (
                      <p className="max-w-xs text-gray-500">{r.error ?? r.summary}</p>
                    )}
                  </td>
                  <td className="text-right">${r.cost_usd.toFixed(4)}</td>
                  <td className="text-right">
                    {r.input_tokens.toLocaleString()} / {r.output_tokens.toLocaleString()}
                  </td>
                  <td className="text-right">
                    {r.duration_s != null ? `${Math.round(r.duration_s)}s` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </aside>
    </div>
  );
}
