"use client";

/**
 * The workspace side panel as a drawer (theme.md §8.3: glass, radius 26, max 380px):
 * Activity | Chat tabs. It slides closed to give the app the full width and reopens
 * from the "Activity" button in the top bar. Desktop: it sits beside the app panel and
 * the app panel grows into the freed space. Below 1024px: it floats over the app and
 * starts closed.
 */
import { PanelRightClose } from "lucide-react";
import { startTransition, type ReactNode } from "react";

export type SideTab = "activity" | "chat";

export function SidePanel({
  open,
  onClose,
  tab,
  onTab,
  activity,
  chat,
}: {
  open: boolean;
  onClose: () => void;
  tab: SideTab;
  onTab: (t: SideTab) => void;
  activity: ReactNode;
  chat: ReactNode;
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
        aria-label="Activity and chat"
        className={`glass ml-auto flex h-full max-lg:bg-white/95 w-[min(380px,calc(100vw-24px))] flex-col rounded-xl shadow-glass transition-transform duration-300 ease-dmx lg:w-[clamp(320px,30vw,380px)] ${
          open ? "translate-x-0" : "translate-x-6"
        }`}
      >
        <div className="flex items-center gap-2 px-3 pt-3 pb-2">
          <div
            role="tablist"
            aria-label="Side panel"
            className="flex flex-1 gap-1 rounded-full bg-[rgb(12_26_46/0.06)] p-1"
          >
            {(["activity", "chat"] as const).map((t) => (
              <button
                key={t}
                role="tab"
                type="button"
                id={`tab-${t}`}
                aria-selected={tab === t}
                aria-controls={`panel-${t}`}
                onClick={() => startTransition(() => onTab(t))}
                className={`h-[38px] flex-1 rounded-full text-sm font-medium capitalize transition-[background-color,color,box-shadow] duration-200 ease-dmx ${
                  tab === t
                    ? "bg-surface text-ink shadow-pill"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Hide panel"
            className="grid size-11 shrink-0 place-items-center rounded-full text-ink-2 transition-colors hover:bg-white/70 hover:text-ink"
          >
            <PanelRightClose size={18} aria-hidden />
          </button>
        </div>
        <div
          role="tabpanel"
          id={`panel-${tab}`}
          aria-labelledby={`tab-${tab}`}
          className="min-h-0 flex-1"
        >
          {tab === "activity" ? (
            <div
              key="activity"
              className="h-full animate-dmx-rise overflow-y-auto px-5 pb-4"
            >
              {activity}
            </div>
          ) : (
            <div key="chat" className="h-full animate-dmx-rise">
              {chat}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
