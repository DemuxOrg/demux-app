"use client";

/**
 * The workspace side panel as a drawer (theme.md §8.4: glass, radius 26, max 380px):
 * the chat. (Activity is hidden for now; `ActivityFeed` is kept for when it returns.)
 * It slides closed to give the app the full width and reopens from the "Chat" button in
 * the top bar. Desktop: it sits beside the app panel and the app panel grows into the
 * freed space. Below 1024px: it floats over the app and starts closed.
 */
import { PanelRightClose } from "lucide-react";
import type { ReactNode } from "react";

export function SidePanel({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      data-open={open}
      aria-hidden={!open}
      inert={!open}
      className="shrink-0 overflow-hidden transition-[width,margin,opacity] duration-300 ease-dmx data-[open=false]:pointer-events-none data-[open=false]:w-0 data-[open=false]:opacity-0 data-[open=true]:w-[min(380px,calc(100vw-24px))] max-lg:fixed max-lg:top-3 max-lg:right-3 max-lg:bottom-3 max-lg:z-30 lg:h-full lg:data-[open=true]:ml-4 lg:data-[open=true]:w-[clamp(320px,30vw,380px)]"
    >
      <aside
        id="side-panel"
        aria-label="Chat"
        className={`glass ml-auto flex h-full max-lg:bg-white/95 w-[min(380px,calc(100vw-24px))] flex-col rounded-xl shadow-glass transition-transform duration-300 ease-dmx lg:w-[clamp(320px,30vw,380px)] ${
          open ? "translate-x-0" : "translate-x-6"
        }`}
      >
        <div className="flex items-center gap-2 pt-3 pr-3 pb-2 pl-5">
          <h2 className="flex-1 text-[15px] font-semibold text-ink">Chat</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Hide chat"
            className="grid size-11 shrink-0 place-items-center rounded-full text-ink-2 transition-colors hover:bg-white/70 hover:text-ink"
          >
            <PanelRightClose size={18} aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1">{children}</div>
      </aside>
    </div>
  );
}
