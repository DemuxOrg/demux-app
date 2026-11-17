"use client";

/**
 * Workspaces page (`/workspaces`): prompt box with example chips + the user's
 * workspaces (max 2). Shows the "Reconnect Gmail" banner and the limit error inline.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import {
  api,
  ApiError,
  countLabel,
  handleAuthError,
  LOGIN_URL,
  type Me,
  type WorkspaceSummary,
} from "@/lib/api";

const EXAMPLES = [
  "Show my unpaid invoices and who I owe",
  "Track my online orders and their delivery status",
  "A board of my job applications by stage",
];
const MAX = 2;

export default function WorkspacesPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [m, ws] = await Promise.all([api.me(), api.listWorkspaces()]);
      setMe(m);
      setWorkspaces(ws);
    } catch (e) {
      if (!handleAuthError(e)) setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const t = setInterval(load, 15000);
    return () => {
      clearTimeout(first);
      clearInterval(t);
    };
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const ws = await api.createWorkspace(prompt.trim());
      router.push(`/workspaces/${ws.id}`);
    } catch (err) {
      if (!handleAuthError(err))
        setError(err instanceof ApiError ? err.message : "Could not create workspace");
      setSubmitting(false);
    }
  }

  const full = (workspaces?.length ?? 0) >= MAX;

  return (
    <div className="mx-auto max-w-3xl space-y-10 px-4 py-10">
      {me?.needs_reconnect && (
        <div className="flex items-center justify-between rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm">
          <span>Demux lost access to your Gmail (Google expires access weekly for test apps). Syncing is paused.</span>
          <a href={LOGIN_URL} className="ml-4 rounded bg-gray-900 px-3 py-1.5 whitespace-nowrap text-white">
            Reconnect Gmail
          </a>
        </div>
      )}

      <form onSubmit={onCreate} className="space-y-3">
        <h1 className="text-2xl font-semibold">What do you want to see from your inbox?</h1>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Show my unpaid invoices and who I owe"
          rows={4}
          maxLength={4000}
          className="w-full rounded border border-gray-300 px-3 py-2"
        />
        <div className="flex flex-wrap items-center gap-2">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex}
              onClick={() => setPrompt(ex)}
              className="rounded-full border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:border-gray-500"
            >
              {ex}
            </button>
          ))}
          <button
            type="submit"
            disabled={submitting || !prompt.trim() || full || me?.needs_reconnect}
            className="ml-auto rounded bg-gray-900 px-5 py-2 text-white disabled:opacity-40"
          >
            {submitting ? "Starting…" : "Build"}
          </button>
        </div>
        {full && (
          <p className="text-sm text-gray-500">
            You have {MAX} workspaces, the limit for now. Delete one to build another.
          </p>
        )}
        {error && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </form>

      <section>
        <h2 className="mb-3 text-lg font-medium">
          Your workspaces {workspaces && `(${workspaces.length} of ${MAX})`}
        </h2>
        {workspaces === null ? (
          <p className="text-gray-500">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {workspaces.map((w) => (
              <Link
                key={w.id}
                href={`/workspaces/${w.id}`}
                className="block rounded-lg border border-gray-200 p-4 hover:border-gray-400"
              >
                <p className="mb-2 truncate font-medium">{w.name}</p>
                <StatusBadge status={w.status} lastSyncedAt={w.last_synced_at} />
                <p className="mt-2 text-sm text-gray-600">{countLabel(w.record_counts)}</p>
              </Link>
            ))}
            {Array.from({ length: Math.max(0, MAX - workspaces.length) }).map((_, i) => (
              <div
                key={i}
                className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-400"
              >
                + empty slot
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
