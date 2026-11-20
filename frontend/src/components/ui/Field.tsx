/** Labelled text input for forms on white cards (theme.md §7.4: every input has a label). */
import type { ComponentProps, ReactNode } from "react";

export function Field({
  label,
  id,
  trailing,
  hint,
  ...input
}: {
  label: string;
  id: string;
  trailing?: ReactNode;
  hint?: ReactNode;
} & ComponentProps<"input">) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-ink-2">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          {...input}
          className={`h-12 w-full rounded-sm border border-line bg-surface px-4 text-base text-ink caret-violet transition-[border-color,box-shadow] duration-150 ease-dmx placeholder:text-ink-3 focus:border-violet-line focus:shadow-[0_0_0_3px_rgb(106_61_240/0.22)] focus:outline-none disabled:opacity-60 ${trailing ? "pr-12" : ""}`}
        />
        {trailing && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-1">
            {trailing}
          </div>
        )}
      </div>
      {hint && <p className="text-[13px] text-ink-3">{hint}</p>}
    </div>
  );
}
