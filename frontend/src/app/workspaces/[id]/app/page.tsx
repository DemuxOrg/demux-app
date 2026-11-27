/**
 * The app alone (`/workspaces/[id]/app`, theme.md §8.4b), opened from More → Open in new
 * tab. It lives outside the `(app)` route group on purpose: no app shell, no sidebar,
 * no bar, only the workspace's app in the whole window.
 */
import type { Metadata } from "next";
import { Suspense } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { WorkspaceAppAlone } from "@/components/WorkspaceAppAlone";

export const metadata: Metadata = { title: "Workspace" };

async function Alone({
  params,
}: Pick<PageProps<"/workspaces/[id]/app">, "params">) {
  const { id } = await params;
  return <WorkspaceAppAlone id={id} />;
}

export default function WorkspaceAppPage(
  props: PageProps<"/workspaces/[id]/app">,
) {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-dvh place-items-center" aria-label="Loading">
          <Spinner size={28} />
        </div>
      }
    >
      <Alone params={props.params} />
    </Suspense>
  );
}
