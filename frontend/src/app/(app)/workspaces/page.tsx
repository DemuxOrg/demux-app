/** `/workspaces`: where sign-in lands. Opens the last workspace, else Create (theme.md §8.0). */
import type { Metadata } from "next";
import { WorkspacesLanding } from "@/components/shell/WorkspacesLanding";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return <WorkspacesLanding />;
}
