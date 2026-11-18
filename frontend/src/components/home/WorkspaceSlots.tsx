/**
 * "Your workspaces · 1 of 2": glass workspace cards (theme.md §7.8) and dashed empty
 * slots. Opening a workspace is a forward navigation.
 */
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { activityLabel } from "@/components/StatusChip";
import { countLabel, timeAgo, type WorkspaceSummary } from "@/lib/api";

export const MAX_WORKSPACES = 2;

function Meta({ w }: { w: WorkspaceSummary }) {
  const busy = activityLabel({ status: w.status });
  if (w.status === "failed")
    return (
      <span className="flex items-center gap-2 text-danger">
        <span aria-hidden className="size-1.5 rounded-full bg-danger" />
        Couldn&apos;t build. Open to try again.
      </span>
    );
  if (busy)
    return (
      <span className="flex items-center gap-2 text-violet-ink">
        <span
          aria-hidden
          className="size-1.5 animate-dmx-pulse rounded-full bg-violet"
        />
        Building your workspace
      </span>
    );
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-live" />
      <span className="truncate">
        Synced {timeAgo(w.last_synced_at)} · {countLabel(w.record_counts)}
      </span>
    </span>
  );
}

export function WorkspaceSlots({
  workspaces,
}: {
  workspaces: WorkspaceSummary[];
}) {
  const free = Math.max(0, MAX_WORKSPACES - workspaces.length);
  return (
    <section className="w-full max-w-[760px]" aria-labelledby="your-workspaces">
      <div className="mb-3 flex items-baseline justify-between px-1">
        <h2 id="your-workspaces" className="text-[15px] font-semibold text-ink">
          Your workspaces
        </h2>
        <span className="text-[13px] text-ink-on-sky tabular">
          {workspaces.length} of {MAX_WORKSPACES}
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
        {workspaces.map((w) => (
          <Link
            key={w.id}
            href={`/workspaces/${w.id}`}
            className="glass group flex items-center gap-3 rounded-lg px-[18px] py-4 shadow-glass transition-[background-color,transform] duration-200 ease-dmx hover:bg-white/85 active:scale-[0.99]"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate text-base font-semibold">
                {w.name}
              </span>
              <span className="mt-1 block text-[13px] text-ink-2">
                <Meta w={w} />
              </span>
            </span>
            <ChevronRight
              size={18}
              aria-hidden
              className="shrink-0 text-ink-3 transition-transform duration-200 ease-dmx group-hover:translate-x-0.5"
            />
          </Link>
        ))}
        {Array.from({ length: free }).map((_, i) => (
          <div
            key={i}
            className="grid min-h-[72px] place-items-center rounded-lg border-[1.5px] border-dashed border-[rgb(12_26_46/0.22)] text-sm text-ink-on-sky"
          >
            {free === 1 ? "One more slot free" : "Slot free"}
          </div>
        ))}
      </div>
      {free === 0 && (
        <p className="mt-3 px-1 text-[13px] text-ink-on-sky">
          You&apos;re using both workspaces. Delete one to build another.
        </p>
      )}
    </section>
  );
}
