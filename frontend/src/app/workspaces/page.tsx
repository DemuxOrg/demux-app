"use client";

/**
 * Workspaces page (`/workspaces`).
 * Responsible for listing the user's workspaces, creating one (name + prompt form),
 * and deleting one. Shows backend errors inline, notably the 409 "limit reached"
 * message. A client component because it is fully interactive.
 */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api, ApiError, type Workspace } from "@/lib/api";

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(
    () =>
      api
        .listWorkspaces()
        .then(setWorkspaces)
        .catch((e) =>
          setError(
            e instanceof Error ? e.message : "Failed to load workspaces",
          ),
        ),
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createWorkspace({ name, prompt });
      setName("");
      setPrompt("");
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create workspace",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: string) {
    setError(null);
    try {
      await api.deleteWorkspace(id);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not delete workspace",
      );
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Workspaces</h1>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      <section>
        {workspaces === null ? (
          <p className="text-gray-500">Loading…</p>
        ) : workspaces.length === 0 ? (
          <p className="text-gray-500">No workspaces yet.</p>
        ) : (
          <ul className="divide-y divide-gray-200 rounded border border-gray-200">
            {workspaces.map((w) => (
              <li
                key={w.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <Link
                    href={`/workspaces/${w.id}`}
                    className="font-medium hover:underline"
                  >
                    {w.name}
                  </Link>
                  <p className="truncate text-sm text-gray-500">{w.prompt}</p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={w.status} />
                  <button
                    onClick={() => onDelete(w.id)}
                    className="text-sm text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <form onSubmit={onCreate} className="space-y-3">
        <h2 className="text-lg font-medium">New workspace</h2>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          className="w-full rounded border border-gray-300 px-3 py-2"
        />
        <textarea
          required
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="What should Demux extract from your email?"
          rows={4}
          className="w-full rounded border border-gray-300 px-3 py-2"
        />
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create workspace"}
        </button>
      </form>
    </div>
  );
}
