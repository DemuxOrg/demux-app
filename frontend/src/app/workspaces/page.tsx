/** `/workspaces`: connect Gmail (no workspace yet), then the prompt and workspace slots. */
import type { Metadata } from "next";
import { HomeScreen } from "@/components/home/HomeScreen";
import { PageTransition } from "@/components/motion/PageTransition";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return (
    <PageTransition>
      <HomeScreen />
    </PageTransition>
  );
}
