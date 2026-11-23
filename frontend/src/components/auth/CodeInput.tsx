"use client";

/**
 * Six-digit code field. One real <input> (so paste, autofill from the email via
 * `autocomplete="one-time-code"`, and screen readers all work) drawn as six boxes.
 */
import { useId, useRef, useState } from "react";

export const CODE_LENGTH = 6;

export function CodeInput({
  value,
  onChange,
  onComplete,
  invalid = false,
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  onComplete?: (v: string) => void;
  invalid?: boolean;
  disabled?: boolean;
}) {
  const id = useId();
  const ref = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  const active = Math.min(value.length, CODE_LENGTH - 1);

  return (
    <div className="relative" onClick={() => ref.current?.focus()}>
      <label htmlFor={id} className="sr-only">
        6-digit code
      </label>
      <input
        ref={ref}
        id={id}
        value={value}
        disabled={disabled}
        autoFocus
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={CODE_LENGTH}
        aria-invalid={invalid || undefined}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => {
          const next = e.target.value.replace(/\D/g, "").slice(0, CODE_LENGTH);
          onChange(next);
          if (next.length === CODE_LENGTH) onComplete?.(next);
        }}
        className="absolute inset-0 z-10 h-full w-full cursor-text opacity-0"
      />
      <div className="grid grid-cols-6 gap-2" aria-hidden>
        {Array.from({ length: CODE_LENGTH }).map((_, i) => {
          const isActive = focused && i === active && !disabled;
          return (
            <div
              key={i}
              className={`grid h-14 place-items-center rounded-sm border bg-surface text-2xl font-medium tabular transition-[border-color,box-shadow] duration-150 ease-dmx ${
                invalid
                  ? "border-danger/40"
                  : isActive
                    ? "border-violet-line shadow-[0_0_0_3px_rgb(106_61_240/0.22)]"
                    : "border-line"
              }`}
            >
              {value[i] ??
                (isActive ? (
                  <span className="h-6 w-px animate-dmx-pulse bg-violet" />
                ) : (
                  ""
                ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
