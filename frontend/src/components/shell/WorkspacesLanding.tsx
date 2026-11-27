"use client";

/**
 * `/workspaces` (theme.md §8.0): the list of the user's workspaces, where sign-in lands.
 * With no workspace yet it opens Create; otherwise it never jumps into one on its own.
 *
 * Only the list is loaded here (the shell's poll: names, statuses, counts). A workspace's
 * app and data load once it is opened. Pointing at or focusing a ready workspace starts
 * loading the app frame, which every workspace shares, so it opens faster.
 */
import { ChevronRight, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
import { Reveal, RevealText } from "@/components/motion/Reveal";
import { activityLabel, WorkspaceDot } from "@/components/StatusChip";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import {
  countLabel,
  loadAppShell,
  timeAgo,
  type WorkspaceSummary,
} from "@/lib/api";
import { lastWorkspace, MAX_WORKSPACES, useShell } from "./AppShell";

const noSubscribe = () => () => {};

export function WorkspacesLanding() {
  const router = useRouter();
  const { workspaces, loadError, reload } = useShell();
  // localStorage exists only in the browser: the server renders no "Last opened" tag.
  const last = useSyncExternalStore(noSubscribe, lastWorkspace, () => null);

  const none = workspaces?.length === 0;
  useEffect(() => {
    if (none) router.replace("/workspaces/new");
  }, [none, router]);

  if (!workspaces || none)
    return (
      <div
        className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center"
        aria-label="Loading"
      >
        {loadError && !workspaces ? (
          <>
            <p role="alert" className="text-base font-medium text-ink">
              {loadError}
            </p>
            <Button variant="secondary" onClick={() => void reload()}>
              Try again
            </Button>
          </>
        ) : (
          // Delayed so a fast load never flashes a spinner.
          <Reveal delay={250}>
            <Spinner size={28} />
          </Reveal>
        )}
      </div>
    );

  const full = workspaces.length >= MAX_WORKSPACES;

  return (
    <main className="flex min-h-dvh flex-col items-center px-4 pb-16">
      <div className="flex w-full max-w-[760px] flex-col gap-6 pt-[clamp(88px,20vh,220px)]">
        <div className="flex flex-col gap-2">
          <RevealText
            text="Your workspaces"
            className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]"
          />
          <Reveal as="p" index={2} className="text-base text-ink-on-sky">
            Open one to see it.
          </Reveal>
        </div>
        <Reveal index={3}>
          <ul className="flex flex-col gap-2.5">
            {workspaces.map((w) => (
              <li key={w.id}>
                <WorkspaceCard w={w} lastOpened={w.id === last} />
              </li>
            ))}
            {!full && (
              <li>
                <Link
                  href="/workspaces/new"
                  className="flex min-h-[72px] items-center justify-center gap-2 rounded-lg border-[1.5px] border-dashed border-[rgb(12_26_46/0.22)] text-sm font-medium text-ink-on-sky transition-colors duration-150 ease-dmx hover:border-[rgb(12_26_46/0.36)] hover:text-ink focus-visible:ring-[3px] focus-visible:ring-violet/25"
                >
                  <Plus size={16} strokeWidth={2.4} aria-hidden /> Create
                  workspace
                </Link>
              </li>
            )}
          </ul>
        </Reveal>
      </div>
    </main>
  );
}

function WorkspaceCard({
  w,
  lastOpened,
}: {
  w: WorkspaceSummary;
  lastOpened: boolean;
}) {
  const label = activityLabel({ status: w.status });
  const meta =
    label ??
    `Synced ${timeAgo(w.last_synced_at)} · ${countLabel(w.record_counts)}`;
  // Ready workspaces open into their app: start loading the frame they all share.
  const warm = label
    ? undefined
    : () => void loadAppShell("v3").catch(() => undefined);

  return (
    <Link
      href={`/workspaces/${w.id}`}
      onPointerEnter={warm}
      onFocus={warm}
      onTouchStart={warm}
      className="group glass dmx-lift flex items-center gap-4 rounded-lg px-[18px] py-4 shadow-glass focus-visible:ring-[3px] focus-visible:ring-violet/25"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-base font-semibold text-ink">
            {w.name}
          </span>
          {lastOpened && (
            <span className="shrink-0 rounded-tag bg-tag px-[7px] py-[3px] text-xs text-ink-2">
              Last opened
            </span>
          )}
        </span>
        <span
          className={`flex min-w-0 items-center gap-2 text-[13px] tabular ${
            label === "Failed" ? "text-danger" : "text-ink-2"
          }`}
        >
          <WorkspaceDot status={w.status} />
          <span className="truncate">{meta}</span>
        </span>
        <span className="truncate text-sm text-ink-3" title={w.prompt}>
          “{w.prompt}”
        </span>
      </span>
      <ChevronRight
        size={18}
        aria-hidden
        className="dmx-nudge shrink-0 text-ink-3"
      />
    </Link>
  );
}
