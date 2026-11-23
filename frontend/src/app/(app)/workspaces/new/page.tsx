/** `/workspaces/new`: connect Gmail if needed, then "Hello, name" and the prompt. */
import type { Metadata } from "next";
import { CreateWorkspace } from "@/components/home/CreateWorkspace";
import { PageTransition } from "@/components/motion/PageTransition";

export const metadata: Metadata = { title: "Create workspace" };

export default function NewWorkspacePage() {
  return (
    <PageTransition>
      <CreateWorkspace />
    </PageTransition>
  );
}
