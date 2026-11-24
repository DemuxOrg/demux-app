"use client";

/**
 * Building blocks of the admin pages (theme.md §7.14): white cards, stat tiles, the
 * range picker, small pills, a data-loading hook and number formatting.
 */
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiError, handleAuthError, type AdminRange } from "@/lib/api";
import { Spinner } from "@/components/ui/Spinner";

// ------------------------------------------------------------------ formatting

const usdFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const numFmt = new Intl.NumberFormat("en-US");
const compactFmt = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Dollars; sub-cent amounts keep 4 decimals so small runs don't read as $0.00. */
export function usd(v: number | null | undefined): string {
  const n = v ?? 0;
  if (n > 0 && n < 0.01) return `$${n.toFixed(4)}`;
  return usdFmt.format(n);
}
export const num = (v: number | null | undefined) => numFmt.format(v ?? 0);
export const compact = (v: number | null | undefined) =>
  compactFmt.format(v ?? 0);

export function day(iso: string): string {
  // Dates from the API are UTC calendar days ("2026-11-03").
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function longDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function duration(s: number | null | undefined): string {
  if (s == null) return "–";
  if (s < 60) return `${Math.round(s)} s`;
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

// ------------------------------------------------------------------ data

type Loaded<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  notFound: boolean;
  reload: () => void;
};

/** Load admin data for `key`; keeps the previous data on screen while a new key loads. */
export function useAdminData<T>(
  key: string,
  load: () => Promise<T>,
): Loaded<T> {
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });
  const [state, setState] = useState<{
    key: string | null;
    data: T | null;
    error: string | null;
    notFound: boolean;
  }>({ key: null, data: null, error: null, notFound: false });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let live = true;
    loadRef
      .current()
      .then((data) => {
        if (live) setState({ key, data, error: null, notFound: false });
      })
      .catch((e: unknown) => {
        if (!live || handleAuthError(e)) return;
        const notFound = e instanceof ApiError && e.status === 404;
        setState((s) => ({
          key,
          data: s.data,
          notFound,
          error: notFound
            ? null
            : e instanceof Error
              ? e.message
              : "Could not load.",
        }));
      });
    return () => {
      live = false;
    };
  }, [key, tick]);

  return {
    data: state.data,
    loading: state.key !== key,
    error: state.error,
    notFound: state.notFound,
    reload,
  };
}

// ------------------------------------------------------------------ layout

export function PageHeader({
  title,
  note,
  right,
}: {
  title: ReactNode;
  note?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 pt-2">
      <div className="min-w-0">
        <h1 className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em] text-balance text-ink">
          {title}
        </h1>
        {note && <p className="mt-2 text-[15px] text-ink-on-sky">{note}</p>}
      </div>
      {right}
    </div>
  );
}

export function Card({
  title,
  note,
  right,
  children,
  className = "",
}: {
  title?: ReactNode;
  note?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`min-w-0 rounded-lg bg-surface px-[22px] py-5 shadow-glass ${className}`}
    >
      {(title || right) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            )}
            {note && <p className="mt-0.5 text-[13px] text-ink-3">{note}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div className="min-w-[160px] flex-1 rounded-lg bg-surface px-5 py-4 shadow-glass">
      <p className="text-[13px] font-medium text-ink-3">{label}</p>
      <p className="tabular mt-1 text-[28px] leading-tight font-medium tracking-[-0.02em] text-ink">
        {value}
      </p>
      {sub && <p className="tabular mt-0.5 text-[13px] text-ink-3">{sub}</p>}
    </div>
  );
}

export function Tiles({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-3">{children}</div>;
}

/** Segmented control (theme.md §7.5). `onGlass` for use inside white cards. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  onWhite = false,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  onWhite?: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={`inline-flex gap-1 rounded-full p-1 ${onWhite ? "bg-ink/[0.06]" : "bg-white/50"}`}
    >
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(o.value)}
            className={`rounded-full px-4 text-sm font-medium whitespace-nowrap transition-colors duration-150 ease-dmx focus-visible:ring-[3px] focus-visible:ring-violet/25 ${
              onWhite ? "h-9" : "h-10"
            } ${selected ? "bg-white text-ink shadow-pill" : "text-ink-2 hover:text-ink"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function RangePicker({
  value,
  onChange,
}: {
  value: AdminRange;
  onChange: (v: AdminRange) => void;
}) {
  return (
    <Segmented<AdminRange>
      label="Date range"
      value={value}
      onChange={onChange}
      options={[
        { value: 7, label: "7 days" },
        { value: 30, label: "30 days" },
        { value: 90, label: "90 days" },
      ]}
    />
  );
}

type Tone = "success" | "danger" | "warning" | "info" | "neutral" | "violet";
const tones: Record<Tone, string> = {
  success: "bg-success-bg text-success",
  danger: "bg-danger-bg text-danger",
  warning: "bg-warning-bg text-warning",
  info: "bg-info-bg text-info",
  neutral: "bg-neutral-bg text-neutral",
  violet: "bg-violet-soft text-violet-ink",
};

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium whitespace-nowrap ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): Tone {
  if (status === "done" || status === "ready") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "building") return "violet";
  if (status === "queued") return "info";
  return "neutral";
}

export function GmailPill({
  connected,
  needsReconnect,
}: {
  connected: boolean;
  needsReconnect: boolean;
}) {
  if (needsReconnect) return <Pill tone="warning">Needs reconnect</Pill>;
  if (connected) return <Pill tone="success">Connected</Pill>;
  return <Pill tone="neutral">Not connected</Pill>;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-16 text-[15px] font-medium text-ink-2">
      <Spinner size={20} />
      {label}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg bg-danger-bg px-5 py-4 text-sm text-danger">
      {message}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-[13px] text-ink-3">{children}</p>;
}
