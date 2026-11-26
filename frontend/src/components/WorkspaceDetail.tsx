"use client";

/**
 * Workspace view (`/workspaces/[id]`, theme.md §8.2–8.3).
 *
 * Lives in the app shell: the sidebar holds navigation and the account (no back button,
 * no avatar here), and the top bar's left padding (`--dmx-gutter`) leaves room for the
 * sidebar's open button while it is closed.
 *
 * - Building: top bar (name, Building chip) + the build progress card.
 * - Failed: the reason and "Try again".
 * - Ready: top bar (name, rename; sync status, ⋯) and the generated app in a white
 *   panel. No Undo and no chat in the MVP. There is no sync button: the worker syncs
 *   every workspace on its own.
 *
 * Polls GET /workspaces/{id} every 2 s while a run is active, every 20 s otherwise, and
 * at once when the page comes back into view (phones pause timers in the background);
 * refetches data / app only when their versions change. A version counts as loaded only
 * once its fetch succeeded, and a failed app-frame fetch is retried, so a dropped
 * request never leaves the page spinning. If loading still takes long, the spinner
 * offers a reload.
 */
import { ChevronLeft, Pencil, X } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  startTransition,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { AppFrame } from "@/components/AppFrame";
import { LogoMark } from "@/components/brand/Logo";
import { StepTransition } from "@/components/motion/PageTransition";
import { rememberWorkspace, useShell } from "@/components/shell/AppShell";
import { StatusChip, SyncStatus } from "@/components/StatusChip";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { BuildFlow } from "@/components/workspace/BuildFlow";
import { MoreMenu } from "@/components/workspace/MoreMenu";
import {
  api,
  ApiError,
  CONNECT_GMAIL_URL,
  handleAuthError,
  loadAppShell,
  type AppDoc,
  type AppRuntime,
  type AppShell,
  type DataDoc,
  type WorkspaceDetail as Detail,
} from "@/lib/api";

export function WorkspaceDetail({ id }: { id: string }) {
  const router = useRouter();
  const { me, workspaces, reload: reloadList } = useShell();
  const [ws, setWs] = useState<Detail | null>(null);
  // The fixed iframe shell per app runtime (v2 inlines the component kit).
  const [shells, setShells] = useState<Partial<Record<AppRuntime, AppShell>>>(
    {},
  );
  const [app, setApp] = useState<AppDoc | null>(null);
  const [data, setData] = useState<DataDoc | null>(null);
  const [error, setError] = useState<string | null>(null); // loading errors
  const [actionError, setActionError] = useState<string | null>(null); // until next action
  const [appError, setAppError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const seen = useRef({ data: -1, app: -1 });

  const refresh = useCallback(async () => {
    try {
      const w = await api.getWorkspace(id);
      startTransition(() => setWs(w));
      const jobs: Promise<unknown>[] = [];
      if (w.data_version !== seen.current.data) {
        const version = w.data_version;
        jobs.push(
          api.getData(id).then((d) => {
            setData(d);
            seen.current.data = version;
          }),
        );
      }
      if (w.app_version !== seen.current.app) {
        const version = w.app_version;
        jobs.push(
          api.getApp(id).then((a) => {
            setApp(a);
            seen.current.app = version;
          }),
        );
      }
      await Promise.all(jobs);
      setError(null);
    } catch (e) {
      if (handleAuthError(e)) return;
      if (e instanceof ApiError && e.status === 404) {
        setError("This workspace doesn't exist, or it was deleted.");
        return;
      }
      setError(
        e instanceof Error ? e.message : "Couldn't load this workspace.",
      );
    }
  }, [id]);

  const runtime = app?.runtime;
  const [shellRetry, setShellRetry] = useState(0);
  useEffect(() => {
    if (!runtime || shells[runtime]) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    loadAppShell(runtime).then(
      (s) => {
        if (live) setShells((x) => ({ ...x, [runtime]: s }));
      },
      () => {
        if (live) timer = setTimeout(() => setShellRetry((n) => n + 1), 3000);
      },
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [runtime, shells, shellRetry]);
  const shell = runtime ? shells[runtime] : undefined;

  useEffect(() => rememberWorkspace(id), [id]);

  // Keep the drawer's row (name, status dot) in step with this page.
  const status = ws?.status;
  const wsName = ws?.name;
  useEffect(() => {
    if (status) void reloadList();
  }, [status, wsName, reloadList]);

  const active = !!ws?.active_run;
  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, active ? 2000 : 20000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh, active]);

  // Phones pause timers while the tab is in the background: catch up on return.
  useEffect(() => {
    const onShow = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onShow);
    window.addEventListener("pageshow", onShow);
    return () => {
      document.removeEventListener("visibilitychange", onShow);
      window.removeEventListener("pageshow", onShow);
    };
  }, [refresh]);

  const onAppError = useCallback((m: string | null) => setAppError(m), []);

  async function act(
    key: string,
    fn: () => Promise<unknown>,
  ): Promise<boolean> {
    setActionError(null);
    setBusyAction(key);
    try {
      await fn();
      await refresh();
      return true;
    } catch (e) {
      if (handleAuthError(e)) return false;
      setActionError(
        e instanceof ApiError ? e.message : "Something went wrong. Try again.",
      );
      await refresh();
      return false;
    } finally {
      setBusyAction(null);
    }
  }

  async function sendMessage(text: string) {
    if (!(await act("message", () => api.sendMessage(id, text)))) {
      throw new Error("not sent"); // keeps the text in the box
    }
  }

  function startRename() {
    if (!ws) return;
    setName(ws.name);
    setRenaming(true);
  }

  async function remove() {
    if (
      !window.confirm(
        "Delete this workspace and everything in it? This can't be undone.",
      )
    )
      return;
    try {
      await api.deleteWorkspace(id);
      const others = workspaces?.some((w) => w.id !== id);
      await reloadList(); // the list no longer shows it
      router.push(others ? "/workspaces" : "/workspaces/new");
    } catch (e) {
      setActionError(
        e instanceof ApiError ? e.message : "Couldn't delete this workspace.",
      );
    }
  }

  if (error && !ws)
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-lg font-medium">{error}</p>
        <ButtonLink href="/workspaces" variant="secondary">
          <ChevronLeft size={16} aria-hidden /> All workspaces
        </ButtonLink>
      </div>
    );
  if (!ws)
    return (
      <div className="grid min-h-dvh place-items-center" aria-label="Loading">
        <SlowLoad size={28} />
      </div>
    );

  const building = ws.status === "building" || ws.active_run?.kind === "build";
  const failed = ws.status === "failed" && !building;
  const ready = !building && !failed;
  const view = building ? "building" : failed ? "failed" : "ready";

  return (
    <div className="flex h-dvh flex-col">
      {/* Top bar (§7.11): sits on the sky, no background of its own. */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 py-[18px] pr-4 pl-[var(--dmx-gutter)] transition-[padding] duration-[360ms] ease-dmx-out sm:pr-6 lg:pr-8">
        <div className="flex min-h-11 min-w-0 flex-1 items-center gap-1 max-sm:basis-full">
          {renaming ? (
            <form
              className="min-w-0 flex-1"
              onSubmit={(e) => {
                e.preventDefault();
                setRenaming(false);
                if (name.trim() && name.trim() !== ws.name)
                  act("rename", () => api.renameWorkspace(id, name.trim()));
              }}
            >
              <label htmlFor="ws-name" className="sr-only">
                Workspace name
              </label>
              <input
                id="ws-name"
                autoFocus
                value={name}
                maxLength={200}
                onChange={(e) => setName(e.target.value)}
                onBlur={(e) => e.currentTarget.form?.requestSubmit()}
                onKeyDown={(e) => e.key === "Escape" && setRenaming(false)}
                className="h-11 w-full max-w-md rounded-full bg-white/80 px-4 text-lg font-semibold tracking-[-0.015em] text-ink caret-violet outline-none focus:shadow-[0_0_0_3px_rgb(106_61_240/0.22)]"
              />
            </form>
          ) : (
            <>
              <h1 className="truncate pl-1 text-lg leading-[1.3] font-semibold tracking-[-0.015em]">
                {ws.name}
              </h1>
              {ready && (
                <button
                  type="button"
                  onClick={startRename}
                  aria-label="Rename workspace"
                  className="grid size-11 shrink-0 place-items-center rounded-full text-ink-on-sky transition-colors hover:bg-white/60"
                >
                  <Pencil size={16} aria-hidden />
                </button>
              )}
              <span className="ml-1">
                <StatusChip
                  status={ws.status}
                  activeKind={ws.active_run?.kind}
                />
              </span>
            </>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {ready && (
            <>
              {!ws.active_run && (
                <span className="mr-1 inline-flex">
                  <SyncStatus lastSyncedAt={ws.last_synced_at} />
                </span>
              )}
              <MoreMenu onRename={startRename} onDelete={remove} />
            </>
          )}
        </div>
      </header>

      {me?.needs_reconnect && (
        <div className="px-4 pb-3 sm:px-6 lg:px-8">
          <div className="glass flex flex-wrap items-center gap-3 rounded-lg px-5 py-3 shadow-glass">
            <p className="min-w-0 flex-1 text-sm">
              Gmail disconnected. Reconnect to keep this workspace updated.
            </p>
            <ButtonLink href={CONNECT_GMAIL_URL} external size="sm">
              Reconnect Gmail
            </ButtonLink>
          </div>
        </div>
      )}
      {(actionError || (error && ws)) && (
        <div className="px-4 pb-3 sm:px-6 lg:px-8" role="alert">
          <div className="flex items-center gap-3 rounded-lg bg-danger-bg py-1 pr-1 pl-5 text-sm text-danger">
            <p className="min-w-0 flex-1 py-2">{actionError || error}</p>
            {actionError && (
              <button
                type="button"
                onClick={() => setActionError(null)}
                aria-label="Dismiss"
                className="grid size-11 place-items-center rounded-full hover:bg-white/60"
              >
                <X size={16} aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      <main className="relative min-h-0 flex-1">
        <StepTransition stepKey={view}>
          {building ? (
            <div className="flex h-full justify-center overflow-y-auto px-4 pt-[clamp(8px,6vh,72px)] pb-16">
              <div className="w-full max-w-[620px]">
                <BuildFlow
                  workspaceId={id}
                  prompt={ws.prompt}
                  run={ws.active_run ?? null}
                  recordCounts={ws.record_counts}
                  onChanged={refresh}
                />
              </div>
            </div>
          ) : failed ? (
            <div className="flex h-full justify-center overflow-y-auto px-4 pt-[clamp(8px,6vh,72px)] pb-16">
              <section className="h-fit w-full max-w-[620px] rounded-2xl bg-surface px-7 pt-9 pb-7 shadow-float sm:px-9">
                <LogoMark size={46} />
                <h2 className="mt-6 text-[30px] leading-[1.1] font-medium tracking-[-0.03em]">
                  We couldn&apos;t build this workspace
                </h2>
                <p className="mt-3 text-base text-ink-2">
                  {ws.last_error?.replace(/^[A-Za-z_]+: /, "") ||
                    "The build stopped before it finished."}
                </p>
                <p className="mt-4 rounded-sm bg-surface-2 px-4 py-3 text-sm text-ink-2">
                  “{ws.prompt}”
                </p>
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={remove}
                    className="rounded text-sm font-medium text-ink-2 hover:text-danger hover:underline"
                  >
                    Delete workspace
                  </button>
                  <Button
                    loading={busyAction === "rebuild"}
                    onClick={() => act("rebuild", () => api.rebuild(id))}
                  >
                    Try again
                  </Button>
                </div>
              </section>
            </div>
          ) : (
            <div className="flex h-full px-3 pb-3 sm:px-4 sm:pb-4">
              <section
                aria-label="Workspace app"
                className="relative min-w-0 flex-1 overflow-hidden rounded-xl bg-surface shadow-panel"
              >
                {app?.html && shell && data ? (
                  <AppFrame
                    shellHead={shell.head}
                    html={app.html}
                    appVersion={app.version}
                    palette={ws.palette}
                    data={data.data}
                    onError={onAppError}
                  />
                ) : (
                  <div
                    className="grid h-full place-items-center"
                    aria-label="Loading the app"
                  >
                    <SlowLoad size={24} />
                  </div>
                )}
                {appError && (
                  <div
                    role="alert"
                    className="absolute inset-x-3 top-3 flex animate-dmx-rise flex-wrap items-center gap-3 rounded-md bg-danger-bg py-1.5 pr-1.5 pl-4 text-sm text-danger shadow-input"
                  >
                    <span className="min-w-0 flex-1">
                      This workspace hit a display error.
                    </span>
                    <Button
                      size="sm"
                      disabled={active}
                      onClick={() =>
                        sendMessage(
                          `The app shows this error, please fix the app: ${appError}`,
                        ).catch(() => undefined)
                      }
                    >
                      Fix it
                    </Button>
                    <button
                      type="button"
                      onClick={() => setAppError(null)}
                      aria-label="Dismiss"
                      className="grid size-11 place-items-center rounded-full hover:bg-white/60"
                    >
                      <X size={16} aria-hidden />
                    </button>
                  </div>
                )}
              </section>
            </div>
          )}
        </StepTransition>
      </main>
    </div>
  );
}

/** A spinner that, if loading takes longer than it should, offers to reload the page. */
function SlowLoad({ size }: { size: number }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 15000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className="flex flex-col items-center gap-4 px-4 text-center">
      <Spinner size={size} />
      {slow && (
        <div className="flex animate-dmx-rise flex-col items-center gap-3">
          <p className="text-sm text-ink-2">
            This is taking longer than usual.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Reload
          </Button>
        </div>
      )}
    </div>
  );
}
