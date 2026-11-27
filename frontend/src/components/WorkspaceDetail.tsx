"use client";

/**
 * Workspace view (`/workspaces/[id]`, theme.md §8.3–8.4).
 *
 * Lives in the app shell: the sidebar holds navigation and the account (no back button,
 * no avatar here).
 *
 * - Building: top bar (name, Building chip) + the build progress card.
 * - Failed: the reason and "Try again".
 * - Ready: the generated app full bleed, edge to edge beside the sidebar (which starts
 *   closed here), so its own look never sits inside Demux's sky. Demux's controls float
 *   over its top-right corner (§7.11 floating bar): sync status or the run chip, and ⋯
 *   (Rename, Open in new tab, Delete). No Undo and no chat in the MVP, no sync button.
 *
 * Loading and polling live in `useWorkspace` (shared with the app-alone page). If
 * loading takes long, the spinner offers a reload.
 */
import { ChevronLeft, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppFrame } from "@/components/AppFrame";
import { LogoMark } from "@/components/brand/Logo";
import { StepTransition } from "@/components/motion/PageTransition";
import {
  rememberWorkspace,
  useFullBleed,
  useShell,
} from "@/components/shell/AppShell";
import { StatusChip, SyncStatus } from "@/components/StatusChip";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { BuildFlow } from "@/components/workspace/BuildFlow";
import { MoreMenu } from "@/components/workspace/MoreMenu";
import { api, ApiError, CONNECT_GMAIL_URL, handleAuthError } from "@/lib/api";
import { saveDraftPrompt } from "@/lib/draft";
import { useWorkspace } from "@/lib/useWorkspace";

export function WorkspaceDetail({ id }: { id: string }) {
  const router = useRouter();
  const { me, workspaces, reload: reloadList } = useShell();
  const { ws, app, data, shell, error, refresh } = useWorkspace(id);
  const [actionError, setActionError] = useState<string | null>(null); // until next action
  const [appError, setAppError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);

  useEffect(() => rememberWorkspace(id), [id]);

  // Keep the drawer's row (name, status dot) in step with this page.
  const status = ws?.status;
  const wsName = ws?.name;
  useEffect(() => {
    if (status) void reloadList();
  }, [status, wsName, reloadList]);

  const active = !!ws?.active_run;
  const buildRun = ws?.active_run?.kind === "build" ? ws.active_run : null;
  const building = ws?.status === "building" || !!buildRun;
  const failed = ws?.status === "failed" && !building;

  // The app (or its loading state) takes the whole page: start with the sidebar closed.
  useFullBleed(ws ? !building && !failed : !error);

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

  /** Cancel a build (theme.md §7.10): the workspace goes, its prompt goes back to Create.
   *  The worker notices the deleted run within 2 s and stops it. */
  async function cancelBuild() {
    if (!ws) return;
    try {
      await api.deleteWorkspace(id);
    } catch (e) {
      if (handleAuthError(e)) return;
      if (!(e instanceof ApiError && e.status === 404)) throw e;
    }
    saveDraftPrompt(ws.prompt);
    router.push("/workspaces/new");
    void reloadList(); // frees the slot in the sidebar and on Create
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

  const view = building ? "building" : failed ? "failed" : "ready";

  const renameForm = (
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
  );

  const banners = (
    <>
      {me?.needs_reconnect && (
        <div className="glass flex flex-wrap items-center gap-3 rounded-lg px-5 py-3 shadow-glass">
          <p className="min-w-0 flex-1 text-sm">
            Gmail disconnected. Reconnect to keep this workspace updated.
          </p>
          <ButtonLink href={CONNECT_GMAIL_URL} external size="sm">
            Reconnect Gmail
          </ButtonLink>
        </div>
      )}
      {(actionError || (error && ws)) && (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-lg bg-danger-bg py-1 pr-1 pl-5 text-sm text-danger shadow-input"
        >
          <p className="min-w-0 flex-1 py-2">{actionError || error}</p>
          {actionError && (
            <DismissButton onClick={() => setActionError(null)} />
          )}
        </div>
      )}
    </>
  );

  if (view === "ready")
    return (
      // Full bleed (§8.4): the app is the page; Demux's controls float over it.
      <main className="relative h-dvh">
        <section aria-label="Workspace app" className="absolute inset-0">
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
        </section>

        {/* Floating bar (§7.11): over the app's top-right corner, as small as it can be. */}
        <div
          className={`glass absolute top-3 right-3 z-10 flex max-w-[calc(100%-96px)] items-center gap-1 rounded-full shadow-glass ${renaming || ws.active_run ? "p-1" : ""}`}
        >
          {renaming ? (
            <div className="flex w-[260px] max-w-full">{renameForm}</div>
          ) : (
            <>
              {ws.active_run && (
                <span className="inline-flex min-w-0 pl-2">
                  <StatusChip
                    status={ws.status}
                    activeKind={ws.active_run.kind}
                  />
                </span>
              )}
              <MoreMenu
                onRename={startRename}
                onDelete={remove}
                newTabHref={`/workspaces/${id}/app`}
                header={<SyncStatus lastSyncedAt={ws.last_synced_at} />}
              />
            </>
          )}
        </div>

        <FloatingBanners>
          {banners}
          {appError && (
            <div
              role="alert"
              className="flex animate-dmx-rise flex-wrap items-center gap-3 rounded-md bg-danger-bg py-1.5 pr-1.5 pl-4 text-sm text-danger shadow-input"
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
              <DismissButton onClick={() => setAppError(null)} />
            </div>
          )}
        </FloatingBanners>
      </main>
    );

  return (
    <div className="flex h-dvh flex-col">
      {/* Top bar (§7.11): sits on the sky, no background of its own. */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 py-[18px] pr-4 pl-[var(--dmx-gutter)] transition-[padding] duration-[360ms] ease-dmx-out sm:pr-6 lg:pr-8">
        <div className="flex min-h-11 min-w-0 flex-1 items-center gap-1 max-sm:basis-full">
          <h1 className="truncate pl-1 text-lg leading-[1.3] font-semibold tracking-[-0.015em]">
            {ws.name}
          </h1>
          <span className="ml-1">
            <StatusChip status={ws.status} activeKind={ws.active_run?.kind} />
          </span>
        </div>
      </header>

      {(me?.needs_reconnect || actionError || (error && ws)) && (
        <div className="flex flex-col gap-3 px-4 pb-3 sm:px-6 lg:px-8">
          {banners}
        </div>
      )}

      <main className="relative min-h-0 flex-1">
        <StepTransition stepKey={view}>
          {building ? (
            <div className="flex h-full justify-center overflow-y-auto px-4 pt-[clamp(8px,6vh,72px)] pb-16">
              <div className="w-full max-w-[520px]">
                <BuildFlow
                  workspaceId={id}
                  prompt={ws.prompt}
                  run={buildRun}
                  onChanged={refresh}
                  onCancel={cancelBuild}
                />
              </div>
            </div>
          ) : (
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
          )}
        </StepTransition>
      </main>
    </div>
  );
}

/** Banners over a full-bleed app: under the floating bar, centered (§7.11). */
export function FloatingBanners({ children }: { children: ReactNode }) {
  return (
    <div className="pointer-events-none absolute inset-x-3 top-[72px] z-10 mx-auto flex max-w-[560px] flex-col gap-2 *:pointer-events-auto">
      {children}
    </div>
  );
}

function DismissButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Dismiss"
      className="grid size-11 place-items-center rounded-full hover:bg-white/60"
    >
      <X size={16} aria-hidden />
    </button>
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
