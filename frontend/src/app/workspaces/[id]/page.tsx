/**
 * Workspace route (`/workspaces/[id]`).
 * Server component whose only job is to read the dynamic `id` param (inside a
 * Suspense boundary, as this Next version requires) and hand it to the interactive
 * <WorkspaceDetail /> client component.
 */
import type { Metadata } from "next";
import { Suspense } from "react";
import { PageTransition } from "@/components/motion/PageTransition";
import { Spinner } from "@/components/ui/Spinner";
import { WorkspaceDetail } from "@/components/WorkspaceDetail";

export const metadata: Metadata = { title: "Workspace" };

async function Detail({
  params,
}: Pick<PageProps<"/workspaces/[id]">, "params">) {
  const { id } = await params;
  return <WorkspaceDetail id={id} />;
}

export default function WorkspaceDetailPage(
  props: PageProps<"/workspaces/[id]">,
) {
  return (
    <PageTransition>
      <Suspense
        fallback={
          <div
            className="grid min-h-dvh place-items-center"
            aria-label="Loading"
          >
            <Spinner size={28} />
          </div>
        }
      >
        <Detail params={props.params} />
      </Suspense>
    </PageTransition>
  );
}
