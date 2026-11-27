"use client";

/**
 * Loads one workspace and keeps it fresh: the workspace (status, runs), its data, its
 * app and the fixed iframe shell for the app's runtime. Used by the workspace page and
 * the app-alone page (theme.md §8.4, §8.4b).
 *
 * Polls GET /workspaces/{id} every 2 s while a run is active, every 20 s otherwise, and
 * at once when the page comes back into view (phones pause timers in the background);
 * refetches data / app only when their versions change. A version counts as loaded only
 * once its fetch succeeded, and a failed shell fetch is retried, so a dropped request
 * never leaves the page spinning. A poll that returns the same workspace keeps the old
 * object, so the page doesn't re-render every 2–20 s for nothing.
 */
import {
  startTransition,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  api,
  ApiError,
  handleAuthError,
  loadAppShell,
  type AppDoc,
  type AppRuntime,
  type AppShell,
  type DataDoc,
  type WorkspaceDetail,
} from "@/lib/api";

/** Same content (polls return fresh objects even when nothing changed). */
export function same<T>(a: T | null, b: T): boolean {
  return a !== null && JSON.stringify(a) === JSON.stringify(b);
}

export const NOT_FOUND = "This workspace doesn't exist, or it was deleted.";

export function useWorkspace(id: string) {
  const [ws, setWs] = useState<WorkspaceDetail | null>(null);
  // The fixed iframe shell per app runtime (v2 inlines the component kit).
  const [shells, setShells] = useState<Partial<Record<AppRuntime, AppShell>>>(
    {},
  );
  const [app, setApp] = useState<AppDoc | null>(null);
  const [data, setData] = useState<DataDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef({ data: -1, app: -1 });

  const refresh = useCallback(async () => {
    try {
      const w = await api.getWorkspace(id);
      // Polls mostly return what we have: keep the same object so nothing re-renders.
      startTransition(() => setWs((prev) => (same(prev, w) ? prev : w)));
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
        setError(NOT_FOUND);
        return;
      }
      setError(
        e instanceof Error ? e.message : "Couldn't load this workspace.",
      );
    }
  }, [id]);

  // Every new app is a studio (v3) app: fetch its shell now, alongside the workspace,
  // instead of after the app arrives (a waterfall of three requests). Cached per page.
  useEffect(() => {
    void loadAppShell("v3").catch(() => undefined);
  }, []);

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

  const active = !!ws?.active_run;
  useEffect(() => {
    const first = setTimeout(refresh, 0);
    // A hidden tab doesn't poll; the visibility handler below catches up on return.
    const timer = setInterval(
      () => {
        if (!document.hidden) void refresh();
      },
      active ? 2000 : 20000,
    );
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

  return { ws, app, data, shell, error, refresh };
}
