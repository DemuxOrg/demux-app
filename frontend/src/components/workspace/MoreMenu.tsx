"use client";

/** The ⋯ menu in the workspace top bar: Rename, Delete. */
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function MoreMenu({
  onRename,
  onDelete,
}: {
  onRename: () => void;
  onDelete: () => void;
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
          className="absolute right-0 z-40 mt-2 w-48 origin-top-right animate-dmx-pop rounded-lg border border-line bg-surface p-1.5 shadow-glass"
        >
          <button
            role="menuitem"
            type="button"
            onClick={pick(onRename)}
            className={`${item} text-ink-2 hover:bg-surface-2 hover:text-ink`}
          >
            <Pencil size={16} aria-hidden /> Rename
          </button>
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
