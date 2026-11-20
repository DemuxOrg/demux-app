"use client";

/**
 * Account row at the bottom of the sidebar (theme.md §7.13), like Claude's: avatar, name
 * and login email. It opens a card above itself with the login email, the connected
 * Gmail, how many workspaces are in use, and Profile (edit name, switch Gmail).
 * Closes on outside click and Escape (Escape here doesn't also close the sidebar).
 */
import { ChevronRight, ChevronsUpDown, Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import type { Me } from "@/lib/api";
import { MAX_WORKSPACES, useShell } from "./AppShell";

/** "Rana Haddad"; accounts created before names were asked fall back to the email. */
export function displayName(me: Me): string {
  return (
    `${me.first_name} ${me.last_name}`.trim() ||
    me.name ||
    me.email.split("@")[0]
  );
}

export function AccountMenu({ onNavigate }: { onNavigate: () => void }) {
  const { me, workspaces } = useShell();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cardId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  if (!me)
    return (
      <div className="flex items-center gap-3 px-2 py-2" aria-hidden>
        <span className="size-9 rounded-full bg-surface-2" />
        <span className="h-3 w-28 rounded-full bg-surface-2" />
      </div>
    );

  const name = displayName(me);
  const initial = name.charAt(0).toUpperCase();

  return (
    <div
      ref={ref}
      className="relative"
      onKeyDown={(e) => {
        if (e.key !== "Escape" || !open) return;
        e.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }}
    >
      {open && (
        <div
          id={cardId}
          role="dialog"
          aria-label="Account"
          className="absolute inset-x-0 bottom-full z-10 mb-2 origin-bottom animate-dmx-pop-up rounded-lg border border-line bg-surface p-2 shadow-panel"
        >
          <div className="px-3 pt-2 pb-3">
            <p className="text-[13px] text-ink-3">Signed in as</p>
            <p className="truncate text-[15px] font-semibold">{me.email}</p>
          </div>
          <div className="flex flex-col gap-2 border-t border-line-soft px-3 py-3 text-[13px] text-ink-2">
            <p className="flex items-center gap-2">
              <Mail size={14} aria-hidden className="shrink-0" />
              <span className="truncate">
                {me.needs_reconnect
                  ? "Gmail needs reconnecting"
                  : me.gmail_connected
                    ? `Reading from ${me.gmail_email ?? "your Gmail"}`
                    : "Gmail not connected"}
              </span>
            </p>
            {workspaces && (
              <p className="tabular">
                {workspaces.length} of {MAX_WORKSPACES} workspaces
              </p>
            )}
          </div>
          <div className="border-t border-line-soft pt-1">
            <Link
              href="/profile"
              onClick={() => {
                setOpen(false);
                onNavigate();
              }}
              className="group flex h-11 items-center gap-3 rounded-sm px-3 text-sm font-medium text-ink-2 transition-colors duration-150 ease-dmx hover:bg-surface-2 hover:text-ink"
            >
              <UserRound size={16} aria-hidden />
              <span className="flex-1">Profile</span>
              <ChevronRight
                size={16}
                aria-hidden
                className="dmx-nudge text-ink-3"
              />
            </Link>
          </div>
        </div>
      )}
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={cardId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors duration-150 ease-dmx hover:bg-surface-2 aria-expanded:bg-surface-2"
      >
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-violet-soft text-[15px] font-semibold text-violet-ink">
          {initial}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink">
            {name}
          </span>
          <span className="block truncate text-[13px] text-ink-3">
            {me.email}
          </span>
        </span>
        <ChevronsUpDown size={16} aria-hidden className="shrink-0 text-ink-3" />
      </button>
    </div>
  );
}
