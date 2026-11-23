/**
 * shadcn-style primitives, restyled to frontend/theme.md (pill buttons, soft status
 * pills, segmented tabs, white cards, blue-tinted shadows). Radix provides behaviour and
 * accessibility for Tabs, Select, Sheet (Dialog) and Tooltip.
 */
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as SelectPrimitive from "@radix-ui/react-select";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cva, type VariantProps } from "class-variance-authority";
import { Check, ChevronDown, Mail, Search, X } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";
import { label as toLabel, latestThread, openEmail, tone as toneOf, type Rec, type Tone } from "../lib/data";

type Children = { children?: React.ReactNode; className?: string };

/* ------------------------------------------------------------------ layout */

const GAP: Record<string, number> = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 };
const gap = (g: number | string | undefined, d: number) =>
  typeof g === "number" ? g : g && GAP[g] !== undefined ? GAP[g] : d;

/** The app's top: title, one line of description, actions on the right. */
export function Page({
  title,
  description,
  actions,
  children,
  className,
}: Children & { title?: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      {(title || description || actions) && (
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            {title && <h1 className="m-0 text-2xl leading-tight font-semibold tracking-[-0.02em] text-ink">{title}</h1>}
            {description && <p className="m-0 mt-1 text-sm text-ink-3">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </div>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className,
}: Children & { title?: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section className={cn("flex flex-col gap-3", className)}>
      {(title || description || actions) && (
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div className="min-w-0">
            {title && <h2 className="m-0 text-[17px] leading-snug font-semibold tracking-[-0.015em] text-ink">{title}</h2>}
            {description && <p className="m-0 mt-0.5 text-[13px] text-ink-3">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stack({ gap: g, children, className }: Children & { gap?: number | string }) {
  return (
    <div className={cn("flex min-w-0 flex-col", className)} style={{ gap: gap(g, 16) }}>
      {children}
    </div>
  );
}

export function Row({
  gap: g,
  align = "center",
  justify = "start",
  wrap = true,
  children,
  className,
}: Children & {
  gap?: number | string;
  align?: "start" | "center" | "end" | "stretch" | "baseline";
  justify?: "start" | "center" | "end" | "between";
  wrap?: boolean;
}) {
  return (
    <div
      className={cn("flex min-w-0", wrap && "flex-wrap", className)}
      style={{
        gap: gap(g, 8),
        alignItems: { start: "flex-start", end: "flex-end", center: "center", stretch: "stretch", baseline: "baseline" }[align],
        justifyContent: { start: "flex-start", end: "flex-end", center: "center", between: "space-between" }[justify],
      }}
    >
      {children}
    </div>
  );
}

/** Responsive grid: as many columns of at least `min` px as fit. */
export function Grid({ min = 240, gap: g, children, className }: Children & { min?: number; gap?: number | string }) {
  return (
    <div
      className={cn("grid min-w-0", className)}
      style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${min}px, 100%), 1fr))`, gap: gap(g, 12) }}
    >
      {children}
    </div>
  );
}

export function Note({ children, className }: Children) {
  return <p className={cn("m-0 text-[13px] text-ink-3", className)}>{children}</p>;
}

export function Separator({ className }: { className?: string }) {
  return <hr className={cn("m-0 h-px border-0 bg-line-soft", className)} />;
}

/* ------------------------------------------------------------------ controls */

const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-full border font-medium whitespace-nowrap transition-[background-color,color,border-color] duration-150 ease-dmx disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-4",
  {
    variants: {
      variant: {
        primary: "border-accent bg-accent text-white hover:border-accent-hover hover:bg-accent-hover",
        secondary:
          "border-[#E3E8F0] bg-[#F5F7FB] text-ink-2 hover:border-accent-line hover:bg-accent-soft hover:text-accent-ink",
        ghost: "border-transparent bg-transparent text-ink-2 hover:bg-surface-2 hover:text-ink",
        link: "h-auto border-transparent bg-transparent p-0 text-accent hover:text-accent-ink hover:underline",
      },
      size: { sm: "h-8 px-3 text-[13px]", md: "h-9 px-3.5 text-sm", icon: "size-9 p-0" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export function Button({
  variant,
  size,
  className,
  type = "button",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size: variant === "link" ? null : size }), className)}
      {...props}
    />
  );
}

const TONE_CLASS: Record<Tone, string> = {
  success: "bg-success-bg text-success",
  danger: "bg-danger-bg text-danger",
  warning: "bg-warning-bg text-warning",
  info: "bg-info-bg text-info",
  neutral: "bg-neutral-bg text-neutral",
};

/** Status pill: soft background, dark text (theme.md §3.4). */
export function Badge({ tone = "neutral", children, className }: Children & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex h-[22px] max-w-full items-center gap-1.5 truncate rounded-full px-2.5 text-xs font-medium whitespace-nowrap",
        TONE_CLASS[tone] ?? TONE_CLASS.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A status value as a pill, its tone picked from the words ("Paid" → green). */
export function StatusBadge({ value, className }: { value: unknown; className?: string }) {
  if (value === null || value === undefined || value === "") return <span className="text-ink-3">—</span>;
  return (
    <Badge tone={toneOf(value)} className={className}>
      {toLabel(String(value))}
    </Badge>
  );
}

export function Tag({ children, className }: Children) {
  return (
    <span className={cn("inline-block rounded-tag bg-tag px-[7px] py-[3px] text-xs leading-tight text-ink-2", className)}>
      {children}
    </span>
  );
}

/** 7px category dot, coloured by series number 1-5 (always next to a text label). */
export function Dot({ series = 2, className }: { series?: number; className?: string }) {
  const n = ((((series - 1) % 5) + 5) % 5) + 1;
  return (
    <span
      aria-hidden
      className={cn("inline-block size-[7px] shrink-0 rounded-full", className)}
      style={{ background: `var(--dmx-series-${n})` }}
    />
  );
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 min-w-0 rounded-full border border-line bg-surface px-3.5 text-sm text-ink caret-accent outline-none placeholder:text-ink-3 focus:border-accent-line focus:shadow-[0_0_0_3px_var(--dmx-accent-ring)]",
        className,
      )}
      {...props}
    />
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search…",
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <label className={cn("relative inline-flex w-[min(280px,100%)] items-center", className)}>
      <Search aria-hidden className="pointer-events-none absolute left-3 size-4 text-ink-3" />
      <Input
        aria-label={placeholder.replace(/…$/, "")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9"
      />
    </label>
  );
}

export type Option = { value: string; label?: React.ReactNode };

/** shadcn Select (Radix). `options` are values or { value, label }. "" means "all". */
export function Select({
  value,
  onChange,
  options,
  placeholder = "All",
  label,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: (string | Option)[];
  placeholder?: string;
  label?: string;
  className?: string;
}) {
  const ALL = "__all__";
  const opts = options.map((o) => (typeof o === "string" ? { value: o, label: toLabel(o) || o } : o));
  return (
    <SelectPrimitive.Root value={value === "" ? ALL : value} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectPrimitive.Trigger
        aria-label={label ?? placeholder}
        className={cn(
          "inline-flex h-9 max-w-full cursor-pointer items-center gap-2 rounded-full border border-line bg-surface px-3.5 text-sm text-ink-2 outline-none hover:border-accent-line data-[state=open]:border-accent-line",
          className,
        )}
      >
        {label && <span className="text-ink-3">{label}:</span>}
        <span className="truncate">
          <SelectPrimitive.Value placeholder={placeholder} />
        </span>
        <ChevronDown aria-hidden className="size-4 text-ink-3" />
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          className="z-50 max-h-[min(320px,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] animate-dmx-pop overflow-hidden rounded-card border border-line bg-surface p-1 shadow-pop"
        >
          <SelectPrimitive.Viewport>
            {[{ value: ALL, label: placeholder }, ...opts].map((o) => (
              <SelectPrimitive.Item
                key={o.value}
                value={o.value}
                className="relative flex h-9 cursor-pointer items-center rounded-[8px] pr-8 pl-3 text-sm text-ink-2 outline-none select-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-ink data-[state=checked]:font-medium data-[state=checked]:text-ink"
              >
                <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-2.5 text-accent">
                  <Check className="size-4" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export type TabItem = { id: string; label: React.ReactNode; content?: React.ReactNode };

/** Segmented tabs (theme.md §7.5). Keeps the chosen tab across data updates. */
export function Tabs({
  tabs,
  value,
  onChange,
  defaultValue,
  toolbar,
  className,
}: {
  tabs: TabItem[];
  value?: string;
  onChange?: (id: string) => void;
  defaultValue?: string;
  toolbar?: React.ReactNode;
  className?: string;
}) {
  const [own, setOwn] = React.useState(defaultValue ?? tabs[0]?.id ?? "");
  const current = value ?? (tabs.some((t) => t.id === own) ? own : (tabs[0]?.id ?? ""));
  return (
    <TabsPrimitive.Root
      value={current}
      onValueChange={(v) => {
        setOwn(v);
        onChange?.(v);
      }}
      className={cn("flex flex-col gap-4", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TabsPrimitive.List className="inline-flex max-w-full gap-1 overflow-x-auto rounded-full bg-[rgba(12,26,46,0.06)] p-1">
          {tabs.map((t) => (
            <TabsPrimitive.Trigger
              key={t.id}
              value={t.id}
              className="h-8 cursor-pointer rounded-full px-3.5 text-sm font-medium whitespace-nowrap text-ink-2 transition-[background-color,color,box-shadow] duration-150 ease-dmx hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-pill"
            >
              {t.label}
            </TabsPrimitive.Trigger>
          ))}
        </TabsPrimitive.List>
        {toolbar && <div className="flex flex-wrap items-center gap-2">{toolbar}</div>}
      </div>
      {tabs.map((t) => (
        <TabsPrimitive.Content key={t.id} value={t.id} className="min-w-0 outline-none">
          {t.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}

/** Side sheet (shadcn Sheet on Radix Dialog). */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  actions,
  children,
}: Children & {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 animate-dmx-fade bg-[rgb(12_26_46/0.18)]" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed top-3 right-3 bottom-3 z-50 flex w-[min(440px,calc(100vw-24px))] animate-dmx-sheet flex-col rounded-panel bg-surface shadow-sheet outline-none"
        >
          <div className="flex items-start gap-3 border-b border-line-soft px-6 pt-5 pb-4">
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="m-0 text-lg leading-snug font-semibold tracking-[-0.015em] text-ink">
                {title}
              </DialogPrimitive.Title>
              {description && <p className="m-0 mt-1 text-[13px] text-ink-3">{description}</p>}
            </div>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close">
                <X />
              </Button>
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>
          {actions && <div className="flex flex-wrap justify-end gap-2 border-t border-line-soft px-6 py-3">{actions}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function Tooltip({ content, children }: { content: React.ReactNode; children: React.ReactElement }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            sideOffset={6}
            className="z-50 max-w-[260px] animate-dmx-fade rounded-[8px] bg-ink px-2.5 py-1.5 text-xs text-white"
          >
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

/* ------------------------------------------------------------------ display */

const AVATAR = ["bg-[#DCE9F9] text-[#1F5FB8]", "bg-[#FCE3D6] text-[#9A3B12]", "bg-[#E9E1FB] text-[#5A33C8]", "bg-[#E4F5EA] text-[#1D6B37]"];

export function Avatar({ name, size = 32, className }: { name: unknown; size?: number; className?: string }) {
  const s = String(name ?? "").trim();
  const initials =
    s
      .split(/[\s@._-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join("") || "?";
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0;
  return (
    <span
      aria-hidden
      className={cn("inline-grid shrink-0 place-items-center rounded-full font-semibold", AVATAR[Math.abs(h) % AVATAR.length], className)}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
    >
      {initials}
    </span>
  );
}

export function Progress({ value, max = 100, className }: { value: number; max?: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / (Number(max) || 1)) * 100 || 0));
  return (
    <div role="progressbar" aria-valuenow={value} aria-valuemax={max} className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-2", className)}>
      <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Card({
  title,
  description,
  footer,
  onClick,
  highlighted,
  children,
  className,
}: Children & {
  title?: React.ReactNode;
  description?: React.ReactNode;
  footer?: React.ReactNode;
  onClick?: () => void;
  highlighted?: boolean;
}) {
  const interactive = !!onClick;
  return (
    <div
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      className={cn(
        "flex min-w-0 flex-col gap-2 rounded-card border border-line bg-surface px-3.5 py-3 text-left",
        interactive &&
          "cursor-pointer transition-[translate,box-shadow,border-color] duration-[250ms] ease-dmx hover:-translate-y-0.5 hover:border-accent-line hover:shadow-pop",
        highlighted && "border-accent-line bg-accent-tint shadow-[0_0_0_3px_var(--dmx-accent-glow)]",
        className,
      )}
    >
      {(title || description) && (
        <div className="min-w-0">
          {title && <div className="text-[15px] leading-snug font-semibold text-ink">{title}</div>}
          {description && <div className="mt-0.5 text-[13px] text-ink-3">{description}</div>}
        </div>
      )}
      {children}
      {footer && <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">{footer}</div>}
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  description = "New matching emails will appear here.",
  className,
}: {
  title?: React.ReactNode;
  description?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-card px-4 py-12 text-center", className)}>
      <p className="m-0 text-[15px] font-medium text-ink-2">{title}</p>
      {description && <p className="m-0 mt-1 text-[13px] text-ink-3">{description}</p>}
    </div>
  );
}

/** "Open email": opens the newest source email of a record in Gmail. */
export function OpenEmail({
  record,
  label = "Open email",
  variant = "link",
}: {
  record: Rec | null | undefined;
  label?: string;
  variant?: "link" | "secondary" | "icon";
}) {
  if (!latestThread(record)) return null;
  if (variant === "icon")
    return (
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={(e) => {
          e.stopPropagation();
          openEmail(record);
        }}
        className="inline-grid size-7 shrink-0 cursor-pointer place-items-center rounded-full border-0 bg-transparent text-ink-3 transition-colors duration-150 hover:bg-accent-soft hover:text-accent-ink"
      >
        <Mail className="size-4" />
      </button>
    );
  return (
    <Button
      variant={variant}
      size={variant === "link" ? undefined : "sm"}
      className={variant === "link" ? "text-[13px]" : undefined}
      onClick={(e) => {
        e.stopPropagation();
        openEmail(record);
      }}
    >
      {variant !== "link" && <Mail />}
      {label}
    </Button>
  );
}
