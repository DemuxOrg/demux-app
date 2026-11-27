/**
 * Workspace status (theme.md §7.6).
 * - <StatusChip>: Building / Syncing / Updating (violet, pulsing dot) or Failed. Ready
 *   shows no chip.
 * - <SyncStatus>: plain "● Synced 3 min ago" text with the live dot, for ready workspaces.
 */
import { timeAgo, type WorkspaceStatus } from "@/lib/api";

type Props = { status: WorkspaceStatus; activeKind?: string | null };

export function activityLabel({ status, activeKind }: Props): string | null {
  if (status === "building" || activeKind === "build") return "Building";
  if (status === "failed") return "Failed";
  if (activeKind === "sync") return "Syncing…";
  if (activeKind === "edit") return "Updating…";
  return null;
}

/** The 7px dot of a workspace row: live green when ready, pulsing violet while
 * building, danger when failed (theme.md §7.13). */
export function WorkspaceDot({ status }: { status: WorkspaceStatus }) {
  const label = activityLabel({ status });
  return (
    <span
      aria-hidden
      className={`size-[7px] shrink-0 rounded-full ${
        label === "Failed"
          ? "bg-danger"
          : label
            ? "animate-dmx-pulse bg-violet"
            : "bg-live"
      }`}
    />
  );
}

export function StatusChip(props: Props) {
  const label = activityLabel(props);
  if (!label) return null;
  const failed = label === "Failed";
  return (
    <span
      className={`inline-flex h-[30px] shrink-0 items-center gap-2 rounded-full px-3 text-[13px] font-medium whitespace-nowrap ${
        failed ? "bg-danger-bg text-danger" : "bg-violet-soft text-violet-ink"
      }`}
    >
      <span
        aria-hidden
        className={`size-[7px] rounded-full ${failed ? "bg-danger" : "animate-dmx-pulse bg-violet"}`}
      />
      {label}
    </span>
  );
}

export function SyncStatus({
  lastSyncedAt,
  className = "text-ink-on-sky",
}: {
  lastSyncedAt: string | null | undefined;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-2 text-[13px] whitespace-nowrap ${className}`}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-live" />
      Synced {timeAgo(lastSyncedAt)}
    </span>
  );
}
