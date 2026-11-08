/**
 * Small colored pill showing a workspace's status (draft / building / ready / failed).
 * Purely presentational; used by the workspace list and detail pages.
 */
import type { WorkspaceStatus } from "@/lib/api";

const STYLES: Record<WorkspaceStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  building: "bg-blue-100 text-blue-700",
  ready: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function StatusBadge({ status }: { status: WorkspaceStatus }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
