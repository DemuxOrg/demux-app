"use client";

/** The ⋯ menu in the workspace bar: Rename, Open in new tab (the app alone), Delete. */
import { ExternalLink, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

export function MoreMenu({
  onRename,
  onDelete,
  newTabHref,
  header,
}: {
  onRename: () => void;
  onDelete: () => void;
  /** The app alone (theme.md §8.4b); the item is hidden without it. */
  newTabHref?: string;
  /** A line above the items (the sync status, when the bar has no room for it). */
  header?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
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

  const item =
    "flex h-11 w-full items-center gap-2.5 rounded-sm px-3 text-left text-sm font-medium transition-colors";
  const pick = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="More"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="grid size-11 place-items-center rounded-full bg-white/60 text-ink transition-colors duration-150 hover:bg-white/90 focus-visible:ring-[3px] focus-visible:ring-violet/25"
      >
        <MoreHorizontal size={20} aria-hidden />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-52 origin-top-right animate-dmx-pop rounded-lg border border-line bg-surface p-1.5 shadow-glass"
        >
          {header && (
            <div className="mb-1 border-b border-line-soft px-3 pt-2 pb-2.5">
              {header}
            </div>
          )}
          <button
            role="menuitem"
            type="button"
            onClick={pick(onRename)}
            className={`${item} text-ink-2 hover:bg-surface-2 hover:text-ink`}
          >
            <Pencil size={16} aria-hidden /> Rename
          </button>
          {newTabHref && (
            <a
              role="menuitem"
              href={newTabHref}
              target="_blank"
              rel="noopener"
              onClick={() => setOpen(false)}
              className={`${item} text-ink-2 hover:bg-surface-2 hover:text-ink`}
            >
              <ExternalLink size={16} aria-hidden /> Open in new tab
            </a>
          )}
          <button
            role="menuitem"
            type="button"
            onClick={pick(onDelete)}
            className={`${item} text-danger hover:bg-danger-bg`}
          >
            <Trash2 size={16} aria-hidden /> Delete
          </button>
        </div>
      )}
    </div>
  );
}
