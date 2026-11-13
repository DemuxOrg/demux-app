"use client";

/**
 * Workspace view (`/workspaces/[id]`).
 *
 * Left: the generated app in a sandboxed iframe (or the live build timeline while
 * building, or the failure message with "Try again"). Right: Activity and Chat tabs.
 * Header: rename, status pill, Sync now, Undo, ⋯ (Rename, Details, Delete).
 *
 * Polls GET /workspaces/{id} every 2 s while a run is active, every 20 s otherwise;
 * refetches data / app only when their versions change.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AppFrame } from "@/components/AppFrame";
import { ChatPanel } from "@/components/ChatPanel";
import { DetailsDrawer } from "@/components/DetailsDrawer";
import { RunTimeline } from "@/components/RunTimeline";
import { StatusBadge } from "@/components/StatusBadge";
import {
  api,
  ApiError,
  handleAuthError,
  type AppDoc,
  type ChangeRead,
  type DataDoc,
  type RunRead,
  type WorkspaceDetail as Detail,
} from "@/lib/api";

export function WorkspaceDetail({ id }: { id: string }) {
  const router = useRouter();
  const [ws, setWs] = useState<Detail | null>(null);
  const [shell, setShell] = useState<string | null>(null);
  const [app, setApp] = useState<AppDoc | null>(null);
  const [data, setData] = useState<DataDoc | null>(null);
  const [changes, setChanges] = useState<ChangeRead[]>([]);
  const [runs, setRuns] = useState<RunRead[]>([]);
  const [tab, setTab] = useState<"activity" | "chat">("activity");
  const [error, setError] = useState<string | null>(null); // loading errors
  const [actionError, setActionError] = useState<string | null>(null); // until next action
  const [appError, setAppError] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [details, setDetails] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const seen = useRef({ data: -1, app: -1, active: "" });

  const loadSide = useCallback(async () => {
    const [c, r] = await Promise.all([api.listChanges(id), api.listRuns(id)]);
    setChanges(c);
    setRuns(r);
  }, [id]);

  const refresh = useCallback(async () => {
    try {
      const w = await api.getWorkspace(id);
      setWs(w);
      const activeKey = w.active_run ? `${w.active_run.id}:${w.active_run.events.length}` : "";
      const jobs: Promise<unknown>[] = [];
      if (w.data_version !== seen.current.data) {
        seen.current.data = w.data_version;
        jobs.push(api.getData(id).then(setData));
      }
      if (w.app_version !== seen.current.app) {
        seen.current.app = w.app_version;
        jobs.push(api.getApp(id).then(setApp));
      }
      if (activeKey !== seen.current.active || jobs.length) {
        seen.current.active = activeKey;
        jobs.push(loadSide());
      }
      await Promise.all(jobs);
      setError(null);
    } catch (e) {
      if (handleAuthError(e)) return;
      if (e instanceof ApiError && e.status === 404) {
        setError("Workspace not found.");
        return;
      }
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [id, loadSide]);

  useEffect(() => {
    api.appShell().then((s) => setShell(s.head)).catch(() => setShell(null));
  }, []);

  const active = !!ws?.active_run;
  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, active ? 2000 : 20000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh, active]);

  const onAppError = useCallback((m: string | null) => setAppError(m), []);

  async function act(fn: () => Promise<unknown>): Promise<boolean> {
    setActionError(null);
    try {
      await fn();
      await refresh();
      return true;
    } catch (e) {
      if (handleAuthError(e)) return false;
      setActionError(e instanceof ApiError ? e.message : "Something went wrong");
      await refresh();
      return false;
    }
  }

  async function sendMessage(text: string) {
    setTab("chat");
    if (!(await act(() => api.sendMessage(id, text)))) {
      throw new Error("not sent"); // keeps the text in the box
    }
  }

  if (error && !ws)
    return (
      <div className="p-8">
        <p className="text-red-600">{error}</p>
        <Link href="/workspaces" className="text-blue-600 hover:underline">
          ← All workspaces
        </Link>
      </div>
    );
  if (!ws) return <p className="p-8 text-gray-500">Loading…</p>;

  const building = ws.status === "building" || ws.active_run?.kind === "build";
  const failed = ws.status === "failed" && !building;

  return (
    <div className="flex h-[calc(100vh-49px)] flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-gray-200 px-4 py-2">
        <Link href="/workspaces" className="text-gray-500 hover:text-gray-900">
          ←
        </Link>
        {renaming ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setRenaming(false);
              if (name.trim()) act(() => api.renameWorkspace(id, name.trim()));
            }}
          >
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setRenaming(false)}
              className="rounded border border-gray-300 px-2 py-0.5"
            />
          </form>
        ) : (
          <h1
            className="max-w-md cursor-pointer truncate font-semibold"
            title="Rename"
            onClick={() => {
              setName(ws.name);
              setRenaming(true);
            }}
          >
            {ws.name} <span className="text-sm text-gray-400">✎</span>
          </h1>
        )}
        <StatusBadge
          status={ws.status}
          lastSyncedAt={ws.last_synced_at}
          activeKind={ws.active_run?.kind}
        />
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => act(() => api.syncNow(id))}
            disabled={active || ws.status !== "ready"}
            className="rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-40"
          >
            Sync now
          </button>
          <button
            onClick={() => act(() => api.undo(id))}
            disabled={!ws.can_undo}
            title="Restore the state before the last run"
            className="rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-40"
          >
            Undo
          </button>
          <div className="relative">
            <button
              onClick={() => setMenu(!menu)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              ⋯
            </button>
            {menu && (
              <div
                className="absolute right-0 z-30 mt-1 w-40 rounded border border-gray-200 bg-white py-1 shadow-lg"
                onMouseLeave={() => setMenu(false)}
              >
                <button
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-gray-50"
                  onClick={() => {
                    setMenu(false);
                    setName(ws.name);
                    setRenaming(true);
                  }}
                >
                  Rename
                </button>
                <button
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-gray-50"
                  onClick={() => {
                    setMenu(false);
                    setDetails(true);
                  }}
                >
                  Details
                </button>
                <button
                  className="block w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-gray-50"
                  onClick={async () => {
                    setMenu(false);
                    if (!window.confirm("Delete this workspace and everything in it?")) return;
                    try {
                      await api.deleteWorkspace(id);
                      router.push("/workspaces");
                    } catch (e) {
                      setActionError(e instanceof ApiError ? e.message : "Delete failed");
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {(actionError || error) && (
        <p className="flex border-b border-red-200 bg-red-50 px-4 py-1.5 text-sm text-red-700">
          <span className="flex-1">{actionError || error}</span>
          {actionError && (
            <button onClick={() => setActionError(null)} aria-label="Dismiss">
              ✕
            </button>
          )}
        </p>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1 bg-gray-50">
          {building ? (
            <div className="mx-auto max-w-xl p-10">
              <h2 className="mb-1 text-lg font-semibold">Building your workspace</h2>
              <p className="mb-6 text-sm text-gray-500">
                This takes a few minutes: the agent explores your mail, decides what to
                track, reads every matching email and writes the interface.
              </p>
              <RunTimeline events={ws.active_run?.events ?? []} />
            </div>
          ) : failed ? (
            <div className="mx-auto max-w-xl p-10">
              <h2 className="mb-2 text-lg font-semibold">This workspace could not be built</h2>
              <p className="mb-6 text-sm text-gray-700">
                {ws.last_error?.replace(/^[A-Za-z_]+: /, "") || "Unknown error."}
              </p>
              <button
                onClick={() => act(() => api.rebuild(id))}
                className="rounded bg-gray-900 px-4 py-2 text-sm text-white"
              >
                Try again
              </button>
            </div>
          ) : app?.html && shell && data ? (
            <>
              <AppFrame
                shellHead={shell}
                html={app.html}
                appVersion={app.version}
                data={data.data}
                onError={onAppError}
              />
              {appError && (
                <div className="absolute inset-x-4 top-4 flex items-center gap-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm shadow">
                  <span className="flex-1">This workspace hit a display error.</span>
                  <button
                    disabled={active}
                    onClick={() =>
                      sendMessage(
                        `The app shows this error, please fix the app: ${appError}`,
                      )
                    }
                    className="rounded bg-gray-900 px-3 py-1 text-white disabled:opacity-40"
                  >
                    Fix it
                  </button>
                  <button onClick={() => setAppError(null)} className="text-gray-500">
                    ✕
                  </button>
                </div>
              )}
            </>
          ) : (
            <p className="p-10 text-gray-500">Loading the app…</p>
          )}
        </div>

        <aside className="flex w-96 shrink-0 flex-col border-l border-gray-200 bg-white">
          <div className="flex border-b border-gray-200">
            {(["activity", "chat"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2 text-sm capitalize ${tab === t ? "border-b-2 border-gray-900 font-medium" : "text-gray-500"}`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "activity" ? (
              <>
                {ws.active_run && ws.active_run.kind !== "build" && (
                  <div className="border-b border-gray-100 p-4">
                    <RunTimeline events={ws.active_run.events} compact />
                  </div>
                )}
                <ActivityFeed changes={changes} runs={runs} />
              </>
            ) : (
              <ChatPanel runs={runs} workspace={ws} onSend={sendMessage} />
            )}
          </div>
        </aside>
      </div>
      {details && <DetailsDrawer workspace={ws} runs={runs} onClose={() => setDetails(false)} />}
    </div>
  );
}
