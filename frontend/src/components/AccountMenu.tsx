"use client";

/**
 * Avatar button (theme.md §7.11: 44px circle, initial, 16/600) with a small menu: the
 * login email, the connected Gmail, and Sign out (better-auth). Closes on outside
 * click and Escape.
 */
import { LogOut, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { authClient } from "@/lib/auth-client";
import type { Me } from "@/lib/api";

export function AccountMenu({ me }: { me: Me | null }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initial = (me?.name || me?.email || " ").trim().charAt(0).toUpperCase();

  async function signOut() {
    setLeaving(true);
    await authClient.signOut().catch(() => undefined);
    router.replace("/login");
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Account"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="grid size-11 place-items-center rounded-full bg-white/60 text-base font-semibold text-ink transition-colors duration-150 hover:bg-white/90 focus-visible:ring-[3px] focus-visible:ring-violet/25"
      >
        {me ? initial : ""}
      </button>
      {open && me && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-72 origin-top-right animate-dmx-rise rounded-lg border border-line bg-surface p-2 shadow-glass"
        >
          <div className="px-3 pt-2 pb-3">
            <p className="text-[13px] text-ink-3">Signed in as</p>
            <p className="truncate text-[15px] font-semibold">{me.email}</p>
          </div>
          <div className="flex items-center gap-2 border-t border-line-soft px-3 py-3 text-[13px] text-ink-2">
            <Mail size={14} aria-hidden className="shrink-0" />
            <span className="truncate">
              {me.gmail_connected
                ? `Reading ${me.gmail_email ?? "your Gmail"}`
                : "Gmail not connected"}
            </span>
          </div>
          <button
            role="menuitem"
            type="button"
            onClick={signOut}
            disabled={leaving}
            className="flex h-11 w-full items-center gap-2 rounded-sm px-3 text-left text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-40"
          >
            <LogOut size={16} aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
