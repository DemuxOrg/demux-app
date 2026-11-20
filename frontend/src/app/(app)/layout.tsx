/**
 * Every signed-in page (/workspaces…, /profile) lives inside the app shell: the sidebar
 * and the data it shares with pages (theme.md §7.13). The route group adds no URL segment.
 */
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

export default function SignedInLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
