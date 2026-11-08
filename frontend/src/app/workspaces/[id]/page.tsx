/**
 * Workspace detail route (`/workspaces/[id]`).
 * Server component whose only job is to read the dynamic `id` param (inside a
 * Suspense boundary, as this Next version requires) and hand it to the interactive
 * <WorkspaceDetail /> client component.
 */
import { Suspense } from "react";
import { WorkspaceDetail } from "@/components/WorkspaceDetail";

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
    <Suspense fallback={<p className="text-gray-500">Loading…</p>}>
      <Detail params={props.params} />
    </Suspense>
  );
}
