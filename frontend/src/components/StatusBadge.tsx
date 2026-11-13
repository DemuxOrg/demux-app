/**
 * Status pill for a workspace: Building…, Syncing…, Synced N min ago, Failed.
 * Purely presentational.
 */
import { timeAgo, type WorkspaceStatus } from "@/lib/api";

export function StatusBadge({
  status,
  lastSyncedAt,
  activeKind,
}: {
  status: WorkspaceStatus;
  lastSyncedAt?: string | null;
  activeKind?: string | null;
}) {
  let label: string;
  let cls: string;
  if (status === "building" || activeKind === "build") {
    label = "Building…";
    cls = "bg-blue-100 text-blue-700";
  } else if (status === "failed") {
    label = "Failed";
    cls = "bg-red-100 text-red-700";
  } else if (activeKind === "sync") {
    label = "Syncing…";
    cls = "bg-blue-100 text-blue-700";
  } else if (activeKind === "edit") {
    label = "Updating…";
    cls = "bg-blue-100 text-blue-700";
  } else if (status === "ready") {
    label = `Synced ${timeAgo(lastSyncedAt)}`;
    cls = "bg-green-100 text-green-700";
  } else {
    label = status;
    cls = "bg-gray-100 text-gray-700";
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${cls}`}
    >
      <span aria-hidden>●</span> {label}
    </span>
  );
}
