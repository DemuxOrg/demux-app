/** `/workspaces`: where sign-in lands. The list of workspaces, else Create (theme.md §8.0). */
import type { Metadata } from "next";
import { PageTransition } from "@/components/motion/PageTransition";
import { WorkspacesLanding } from "@/components/shell/WorkspacesLanding";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return (
    <PageTransition>
      <WorkspacesLanding />
    </PageTransition>
  );
}
