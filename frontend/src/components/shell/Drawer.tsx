"use client";

/**
 * The app sidebar's contents (theme.md §7.13): the lockup with the close button on its
 * right, Create workspace (while a slot is free), the Workspaces disclosure, and the
 * account row at the bottom (its card holds Profile and Log out). It stays mounted; AppShell and globals.css open
 * and close it, and `inert` keeps a closed sidebar out of the tab order.
 */
import { ChevronDown, PanelLeftClose, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useId, useState, type CSSProperties, type Ref } from "react";
import { Lockup } from "@/components/brand/Logo";
import { activityLabel } from "@/components/StatusChip";
import { Spinner } from "@/components/ui/Spinner";
import type { WorkspaceSummary } from "@/lib/api";
import { AccountMenu } from "./AccountMenu";
import { DRAWER_ID, MAX_WORKSPACES, useShell } from "./AppShell";

/** Stagger position of a sidebar row (`--i`, read by `dmx-drawer-item`). */
const step = (i: number) => ({ "--i": i }) as CSSProperties;

type Props = {
  open: boolean;
  closeRef: Ref<HTMLButtonElement>;
  onClose: () => void;
  onNavigate: () => void;
};

export function Drawer(props: Props) {
  // The current page highlights its row. The URL is only known at request time, so the
  // sidebar first renders without a highlight and the live one streams in.
  return (
    <Suspense fallback={<DrawerPanel {...props} pathname={null} />}>
      <LiveDrawer {...props} />
    </Suspense>
  );
}

function LiveDrawer(props: Props) {
  return <DrawerPanel {...props} pathname={usePathname()} />;
}

function DrawerPanel({
  open,
  closeRef,
  onClose,
  onNavigate,
  pathname,
}: Props & { pathname: string | null }) {
  const { workspaces } = useShell();
  const full = (workspaces?.length ?? 0) >= MAX_WORKSPACES;
  const creating = pathname === "/workspaces/new";

  return (
    <nav
      id={DRAWER_ID}
      aria-label="Workspaces and account"
      inert={!open}
      className="dmx-sidebar-panel absolute top-3 bottom-3 left-3 flex w-[min(300px,calc(100vw-24px))] flex-col rounded-xl bg-surface p-3 shadow-panel"
    >
      <div className="dmx-drawer-item -mt-1.5 flex h-11 items-center justify-between gap-2">
        <Link
          href="/workspaces"
          onClick={onNavigate}
          aria-label="Demux home"
          className="rounded-full px-2 py-1.5"
        >
          <Lockup size={28} />
        </Link>
        <button
          ref={closeRef}
          type="button"
          aria-label="Close sidebar"
          aria-expanded={open}
          aria-controls={DRAWER_ID}
          onClick={onClose}
          className="grid size-11 shrink-0 place-items-center rounded-full text-ink-3 transition-[background-color,color,transform] duration-200 ease-dmx hover:bg-surface-2 hover:text-ink focus-visible:ring-[3px] focus-visible:ring-violet/25 active:scale-95"
        >
          <PanelLeftClose size={20} aria-hidden />
        </button>
      </div>

      {!full && (
        <div style={step(1)} className="dmx-drawer-item mt-5">
          <Link
            href="/workspaces/new"
            onClick={onNavigate}
            aria-current={creating ? "page" : undefined}
            className="group flex h-11 items-center gap-3 rounded-full pr-4 pl-2 text-[15px] font-medium text-ink transition-colors duration-150 ease-dmx hover:bg-surface-2 aria-[current=page]:bg-violet-soft aria-[current=page]:text-violet-ink"
          >
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-violet-soft text-violet transition-colors duration-150 ease-dmx group-aria-[current=page]:bg-surface">
              <Plus size={16} strokeWidth={2.4} aria-hidden />
            </span>
            Create workspace
          </Link>
        </div>
      )}

      <WorkspaceList
        workspaces={workspaces}
        full={full}
        pathname={pathname}
        onNavigate={onNavigate}
        className={full ? "mt-5" : "mt-3"}
      />

      <div
        style={step(4)}
        className="dmx-drawer-item mt-auto flex flex-col border-t border-line-soft pt-3"
      >
        <AccountMenu onNavigate={onNavigate} />
      </div>
    </nav>
  );
}

function WorkspaceList({
  workspaces,
  full,
  pathname,
  onNavigate,
  className,
}: {
  workspaces: WorkspaceSummary[] | null;
  full: boolean;
  pathname: string | null;
  onNavigate: () => void;
  className: string;
}) {
  const listId = useId();
  const [open, setOpen] = useState(true);

  return (
    <section style={step(2)} className={`dmx-drawer-item ${className}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
        className="flex h-11 w-full items-center gap-1.5 rounded-full px-3 text-[13px] font-medium text-ink-3 transition-colors duration-150 ease-dmx hover:text-ink-2"
      >
        Workspaces
        <ChevronDown
          size={14}
          strokeWidth={2.2}
          aria-hidden
          className={`transition-transform duration-200 ease-dmx ${open ? "" : "-rotate-90"}`}
        />
        {workspaces && (
          <span className="ml-auto font-normal tabular">
            {workspaces.length} of {MAX_WORKSPACES}
          </span>
        )}
      </button>

      {/* Height animates through grid rows 0fr ↔ 1fr. */}
      <div
        id={listId}
        inert={!open}
        className="grid transition-[grid-template-rows,opacity] duration-300 ease-dmx-out"
        style={{
          gridTemplateRows: open ? "1fr" : "0fr",
          opacity: open ? 1 : 0,
        }}
      >
        <div className="min-h-0 overflow-hidden">
          {workspaces === null ? (
            <div className="px-3 py-3" aria-label="Loading workspaces">
              <Spinner size={16} />
            </div>
          ) : workspaces.length === 0 ? (
            <p className="px-3 pt-1 pb-2 text-[13px] text-ink-3">
              No workspaces yet
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {workspaces.map((w) => (
                <li key={w.id}>
                  <WorkspaceRow
                    w={w}
                    active={pathname === `/workspaces/${w.id}`}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          )}
          {full && (
            <p className="px-3 pt-2 text-[13px] text-ink-3">
              You&apos;re using both workspaces. Delete one to build another.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function WorkspaceRow({
  w,
  active,
  onNavigate,
}: {
  w: WorkspaceSummary;
  active: boolean;
  onNavigate: () => void;
}) {
  const label = activityLabel({ status: w.status });
  const failed = label === "Failed";
  return (
    <Link
      href={`/workspaces/${w.id}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      title={w.name}
      className="flex h-11 items-center gap-3 rounded-full px-3 text-sm font-medium text-ink-2 transition-colors duration-150 ease-dmx hover:bg-surface-2 hover:text-ink aria-[current=page]:bg-violet-soft aria-[current=page]:text-violet-ink"
    >
      <span
        aria-hidden
        className={`size-[7px] shrink-0 rounded-full ${
          failed
            ? "bg-danger"
            : label
              ? "animate-dmx-pulse bg-violet"
              : "bg-live"
        }`}
      />
      <span className="min-w-0 flex-1 truncate">{w.name}</span>
      {label && (
        <span
          className={`shrink-0 text-xs ${failed ? "text-danger" : "text-ink-3"}`}
        >
          {label}
        </span>
      )}
    </Link>
  );
}
