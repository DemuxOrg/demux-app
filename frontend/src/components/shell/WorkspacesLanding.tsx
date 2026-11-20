"use client";

/**
 * `/workspaces` has no screen of its own: once the list is loaded it opens the workspace
 * used last in this browser, else the newest one, else Create.
 */
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Reveal } from "@/components/motion/Reveal";
import { Spinner } from "@/components/ui/Spinner";
import { lastWorkspace, useShell } from "./AppShell";

export function WorkspacesLanding() {
  const router = useRouter();
  const { workspaces } = useShell();

  useEffect(() => {
    if (!workspaces) return;
    const last = lastWorkspace();
    const target = workspaces.find((w) => w.id === last) ?? workspaces.at(-1);
    router.replace(target ? `/workspaces/${target.id}` : "/workspaces/new");
  }, [workspaces, router]);

  return (
    <div className="grid min-h-dvh place-items-center" aria-label="Loading">
      {/* Delayed so a fast load never flashes a spinner. */}
      <Reveal delay={250}>
        <Spinner size={28} />
      </Reveal>
    </div>
  );
}
