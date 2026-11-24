"use client";

/**
 * Admin shell (theme.md §7.14): sky, a top bar with the lockup, the section tabs and
 * "Back to Demux". It asks `/me` whether the user is an admin; the API also refuses
 * every admin call to anyone else (404), so this check only decides what to render.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Lockup } from "@/components/brand/Logo";
import { ButtonLink } from "@/components/ui/Button";
import { api, handleAuthError, type Me } from "@/lib/api";
import { Loading } from "./ui";

const TABS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/demo", label: "Demo inbox" },
];

function activeTab(path: string): string {
  if (path.startsWith("/admin/users") || path.startsWith("/admin/workspaces"))
    return "/admin/users";
  if (path.startsWith("/admin/demo")) return "/admin/demo";
  return "/admin";
}

export function AdminShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e) => {
        if (!handleAuthError(e)) setFailed(true);
      });
  }, []);

  const current = activeTab(path);
  const allowed = me?.is_admin === true;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 px-6 pt-[18px] pb-4">
        <div className="flex items-center gap-3">
          <Link href="/" aria-label="Demux home" className="rounded-full">
            <Lockup size={28} />
          </Link>
          <span className="text-sm font-medium text-ink-on-sky">Admin</span>
        </div>
        {allowed && (
          <nav aria-label="Admin sections">
            <ul className="flex gap-1 rounded-full bg-white/50 p-1">
              {TABS.map((t) => {
                const selected = t.href === current;
                return (
                  <li key={t.href}>
                    <Link
                      href={t.href}
                      aria-current={selected ? "page" : undefined}
                      className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition-colors duration-150 ease-dmx focus-visible:ring-[3px] focus-visible:ring-violet/25 ${
                        selected
                          ? "bg-white text-ink shadow-pill"
                          : "text-ink-2 hover:text-ink"
                      }`}
                    >
                      {t.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        )}
        <ButtonLink href="/workspaces" variant="secondary">
          Back to Demux
        </ButtonLink>
      </header>
      <main className="mx-auto flex w-full max-w-[1240px] flex-1 flex-col gap-4 px-6 pb-12">
        {failed ? (
          <p className="py-16 text-[15px] text-ink-on-sky">
            Could not reach Demux. Try again in a minute.
          </p>
        ) : !me ? (
          <Loading />
        ) : !allowed ? (
          <div className="mx-auto mt-16 w-full max-w-[440px] rounded-2xl bg-surface p-8 text-center shadow-float">
            <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink">
              Page not found
            </h1>
            <p className="mt-2 text-[15px] text-ink-2">
              This page does not exist.
            </p>
          </div>
        ) : (
          children
        )}
      </main>
      {allowed && (
        <footer className="px-6 pb-6 text-center text-[13px] text-ink-on-sky">
          Shown: prompts, edit messages, counts and costs. Never email content.
        </footer>
      )}
    </div>
  );
}
