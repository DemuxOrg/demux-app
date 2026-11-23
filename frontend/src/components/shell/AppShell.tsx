"use client";

/**
 * Signed-in app shell (theme.md §7.13, §8). The `(app)` route group's layout renders it,
 * so pages change inside it and it never re-mounts.
 *
 * - Data: the user (`/me`) and the workspace list, polled every 15 s. Pages read them
 *   with `useShell()` and call `reload()` after they change something the sidebar shows.
 * - Layout, like Notion: from 768px the sidebar sits beside the page and pushes it, so
 *   closing it gives the page the full width. Below 768px it floats over the page with a
 *   scrim. The close button is on the right of the sidebar header; while the sidebar is
 *   closed, an open button sits at the top left of the page.
 * - `data-drawer`: "auto" (open from 768px, closed below) until the user toggles, then
 *   "open" or "closed". The CSS lives in globals.css (`dmx-shell`, `dmx-sidebar`…). Pages
 *   pad their top bar by `var(--dmx-gutter)`: room for the open button, or not.
 * - A click anywhere outside the sidebar closes it, at every width (also a click into a
 *   workspace's app, whose iframe reports only as the window losing focus).
 */
import { PanelLeftOpen } from "lucide-react";
import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  api,
  handleAuthError,
  type Me,
  type WorkspaceSummary,
} from "@/lib/api";
import { Drawer } from "./Drawer";

export const MAX_WORKSPACES = 2;
const POLL_MS = 15000;
export const DRAWER_ID = "app-sidebar";
const DESKTOP = "(min-width: 768px)";

type Shell = {
  me: Me | null;
  workspaces: WorkspaceSummary[] | null;
  /** Set when the last load failed for a reason other than a missing session. */
  loadError: string | null;
  reload: () => Promise<void>;
};

const ShellContext = createContext<Shell | null>(null);

export function useShell(): Shell {
  const shell = useContext(ShellContext);
  if (!shell) throw new Error("useShell() needs <AppShell> above it");
  return shell;
}

function subscribeDesktop(onChange: () => void) {
  const query = window.matchMedia(DESKTOP);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True from 768px. The server renders the desktop layout; phones correct it on hydration. */
function useDesktop(): boolean {
  return useSyncExternalStore(
    subscribeDesktop,
    () => window.matchMedia(DESKTOP).matches,
    () => true,
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [m, ws] = await Promise.all([api.me(), api.listWorkspaces()]);
      startTransition(() => {
        setMe(m);
        setWorkspaces(ws);
        setLoadError(null);
      });
    } catch (e) {
      if (!handleAuthError(e))
        setLoadError(
          e instanceof Error ? e.message : "Couldn't load your workspaces.",
        );
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(reload, 0);
    const timer = setInterval(reload, POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [reload]);

  const desktop = useDesktop();
  const [drawer, setDrawer] = useState<"auto" | "open" | "closed">("auto");
  const open = drawer === "open" || (drawer === "auto" && desktop);
  const openRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // After a toggle, focus moves to the other toggle (the one that just appeared).
  const focusNext = useRef<"open" | "close" | null>(null);

  const setOpen = useCallback((next: boolean) => {
    focusNext.current = next ? "close" : "open";
    setDrawer(next ? "open" : "closed");
  }, []);

  useEffect(() => {
    const target = focusNext.current === "close" ? closeRef : openRef;
    if (focusNext.current) target.current?.focus({ preventScroll: true });
    focusNext.current = null;
  }, [open]);

  // On a phone the sidebar covers the page: Escape closes it, and so does choosing a page.
  useEffect(() => {
    if (!open || desktop) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, desktop, setOpen]);
  // Click outside closes. Capture phase, on "click" rather than "pointerdown": the clicked
  // control still gets its click before the page reflows into the freed space. Focus is
  // left where the user clicked (no move to the open button).
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        sidebarRef.current?.contains(target) ||
        openRef.current?.contains(target)
      )
        return;
      setDrawer("closed");
    };
    const onBlur = () => {
      if (document.activeElement?.tagName === "IFRAME") setDrawer("closed");
    };
    document.addEventListener("click", onClick, true);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("blur", onBlur);
    };
  }, [open]);

  const onNavigate = useCallback(() => {
    if (!desktop) setDrawer("closed");
  }, [desktop]);

  const shell = useMemo(
    () => ({ me, workspaces, loadError, reload }),
    [me, workspaces, loadError, reload],
  );

  return (
    <ShellContext.Provider value={shell}>
      <div className="dmx-shell flex min-h-dvh flex-1" data-drawer={drawer}>
        <div
          aria-hidden
          onClick={() => setOpen(false)}
          className="dmx-scrim fixed inset-0 z-30 bg-[rgb(12_26_46/0.18)]"
        />
        <aside
          ref={sidebarRef}
          className="dmx-sidebar fixed inset-y-0 left-0 z-40 md:sticky md:top-0 md:h-dvh md:shrink-0 md:overflow-hidden"
        >
          <Drawer
            open={open}
            closeRef={closeRef}
            onClose={() => setOpen(false)}
            onNavigate={onNavigate}
          />
        </aside>
        <div className="min-w-0 flex-1">
          <button
            ref={openRef}
            type="button"
            aria-label="Open sidebar"
            aria-expanded={open}
            aria-controls={DRAWER_ID}
            onClick={() => setOpen(true)}
            className="dmx-open-toggle fixed top-[18px] left-6 z-20 grid size-11 place-items-center rounded-full bg-white/60 text-ink hover:bg-white/90 focus-visible:ring-[3px] focus-visible:ring-violet/25 active:scale-95"
          >
            <PanelLeftOpen size={20} aria-hidden />
          </button>
          {children}
        </div>
      </div>
    </ShellContext.Provider>
  );
}

const LAST_KEY = "demux.lastWorkspace";

/** Remember the workspace opened last in this browser (where /workspaces lands). */
export function rememberWorkspace(id: string) {
  try {
    localStorage.setItem(LAST_KEY, id);
  } catch {
    /* storage unavailable */
  }
}

export function lastWorkspace(): string | null {
  try {
    return localStorage.getItem(LAST_KEY);
  } catch {
    return null;
  }
}
