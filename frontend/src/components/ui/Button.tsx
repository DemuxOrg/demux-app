/**
 * Buttons (theme.md §7.1). One `primary` (violet) per screen.
 *
 * - primary:   violet pill, 48px (44px with size="sm", used inside panels)
 * - secondary: glass pill on the sky (Sync now, Undo)
 * - quiet:     neutral pill on white surfaces (Cancel, secondary actions in cards)
 * - icon:      44px glass circle on the sky, needs `aria-label`
 * - ghost:     44px transparent circle (rename)
 *
 * `loading` keeps the width and swaps the label for a spinner.
 */
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "quiet" | "icon" | "ghost";

const base =
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background-color,color,box-shadow,opacity,transform] duration-150 ease-dmx focus-visible:ring-[3px] focus-visible:ring-violet/25 disabled:cursor-not-allowed disabled:opacity-40 active:scale-[0.98] disabled:active:scale-100";

const variants: Record<Variant, string> = {
  primary:
    "rounded-full bg-violet px-[22px] text-base text-white hover:bg-violet-hover disabled:hover:bg-violet",
  secondary:
    "h-11 rounded-full bg-white/60 px-4 text-sm text-ink hover:bg-white/90 disabled:hover:bg-white/60",
  quiet:
    "h-11 rounded-full border border-chip-line bg-surface-3 px-4 text-sm text-ink-2 hover:border-violet-line hover:bg-violet-soft hover:text-violet-ink",
  icon: "size-11 rounded-full bg-white/60 text-ink hover:bg-white/90",
  ghost: "size-11 rounded-full text-ink-on-sky hover:bg-white/60",
};

function classes(variant: Variant, size: "md" | "sm", className = "") {
  const height = variant === "primary" ? (size === "sm" ? "h-11" : "h-12") : "";
  return `${base} ${variants[variant]} ${height} ${className}`;
}

type Common = {
  variant?: Variant;
  size?: "md" | "sm";
  loading?: boolean;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: Common & ComponentProps<"button">) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={classes(variant, size, className)}
    >
      <span
        className={`inline-flex items-center gap-2 ${loading ? "invisible" : ""}`}
      >
        {children}
      </span>
      {loading && (
        <span className="absolute inset-0 grid place-items-center">
          <Spinner size={16} light={variant === "primary"} />
        </span>
      )}
    </button>
  );
}

/** Same looks for navigation. External/backend URLs use a plain <a>. */
export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  children,
  href,
  external = false,
  ...rest
}: Omit<Common, "loading"> & { href: string; external?: boolean } & Omit<
    ComponentProps<"a">,
    "href"
  >) {
  const cls = classes(variant, size, className);
  if (external)
    return (
      <a href={href} className={cls} {...rest}>
        {children}
      </a>
    );
  return (
    <Link href={href} className={cls} {...rest}>
      {children}
    </Link>
  );
}
