"use client";

/**
 * Client component for the workspace detail view.
 * Responsible for fetching and showing one workspace's name, prompt and status. The actual
 * workspace view (tables / cards / Kanban) is a placeholder until a later phase.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api, ApiError, type Workspace } from "@/lib/api";

export function WorkspaceDetail({ id }: { id: string }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getWorkspace(id)
      .then(setWorkspace)
      .catch((e) =>
        setError(
          e instanceof ApiError ? e.message : "Failed to load workspace",
        ),
      );
  }, [id]);

  return (
    <div className="space-y-6">
      <Link
        href="/workspaces"
        className="text-sm text-blue-600 hover:underline"
      >
        ← All workspaces
      </Link>
      {error && <p className="text-red-600">{error}</p>}
      {!workspace && !error && <p className="text-gray-500">Loading…</p>}
      {workspace && (
        <>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{workspace.name}</h1>
            <StatusBadge status={workspace.status} />
          </div>
          <p className="whitespace-pre-wrap text-gray-700">
            {workspace.prompt}
          </p>
          <div className="rounded border border-dashed border-gray-300 p-10 text-center text-gray-500">
            Workspace view coming soon
          </div>
        </>
      )}
    </div>
  );
}
