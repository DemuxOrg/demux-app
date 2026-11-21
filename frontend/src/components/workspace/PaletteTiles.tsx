"use client";

/**
 * The five palette tiles (theme.md §7.10 step 1, §8 ⋯ → Look): a radio group where each
 * tile previews its palette with no real data (an accent pill, a soft tag, three bars in
 * series 1-3). Selection uses Demux's own violet whatever the tile's palette.
 *
 * `onChange` fires for every change (arrow keys preview palettes one by one); `onPick`
 * fires only when a pointer chose the tile, so a menu can close on click but stay open
 * while the keyboard moves through it.
 */
import { Check } from "lucide-react";
import { useId, useRef } from "react";
import type { PaletteId, PaletteInfo } from "@/lib/api";

const BARS = ["55%", "85%", "38%"];

export function PaletteTiles({
  palettes,
  value,
  onChange,
  onPick,
  label,
  className = "grid grid-cols-3 gap-2.5",
}: {
  palettes: PaletteInfo[];
  value: PaletteId;
  onChange: (id: PaletteId) => void;
  onPick?: () => void;
  label: string;
  className?: string;
}) {
  const name = useId();
  const pointer = useRef(false);

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={className}
      onPointerDown={() => (pointer.current = true)}
      onKeyDown={() => (pointer.current = false)}
    >
      {palettes.map((p) => {
        const selected = p.id === value;
        return (
          <label
            key={p.id}
            className={`relative flex cursor-pointer flex-col gap-2 rounded-md bg-surface transition-[translate,scale,box-shadow,border-color] duration-[250ms] ease-dmx hover:-translate-y-0.5 hover:shadow-glass active:scale-[0.99] has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-violet/25 ${
              selected
                ? "border-2 border-violet p-[9px]"
                : "border border-line p-2.5"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={p.id}
              checked={selected}
              onChange={() => {
                onChange(p.id);
                if (pointer.current) onPick?.();
                pointer.current = false;
              }}
              className="sr-only"
            />
            <span
              aria-hidden
              className="flex h-16 flex-col justify-between rounded-sm bg-surface-2 p-2.5"
            >
              <span className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-7 rounded-full"
                  style={{ background: p.accent }}
                />
                <span
                  className="h-2.5 w-5 rounded-tag"
                  style={{ background: p.accent_soft }}
                />
              </span>
              <span className="flex h-6 items-end gap-1">
                {BARS.map((h, i) => (
                  <span
                    key={h}
                    className="w-2 rounded-[2px]"
                    style={{ height: h, background: p.series[i] }}
                  />
                ))}
              </span>
            </span>
            <span className="text-sm font-medium text-ink">{p.name}</span>
            {selected && (
              <span
                aria-hidden
                className="absolute top-1.5 right-1.5 grid size-5 place-items-center rounded-full bg-violet text-white"
              >
                <Check size={12} strokeWidth={3} />
              </span>
            )}
          </label>
        );
      })}
    </div>
  );
}
