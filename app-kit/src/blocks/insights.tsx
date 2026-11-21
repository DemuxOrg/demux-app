/**
 * Numbers and charts: StatCard, StatRow, Chart (shadcn charts on Recharts), Dashboard.
 * Colours come from the palette's series (--dmx-series-1…5, "Other" in series-other).
 */
import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "../lib/cn";
import { fmt, type Point, type Tone } from "../lib/data";
import { Card, EmptyState, Grid, Stack } from "../ui/primitives";

const SERIES = [1, 2, 3, 4, 5].map((n) => `var(--dmx-series-${n})`);
const OTHER = "var(--dmx-series-other)";
const TICK = { fill: "var(--dmx-ink-3)", fontSize: 12 };

type ValueFormat = "number" | "money" | "percent";

function show(v: unknown, format: ValueFormat = "number", currency?: string): string {
  if (format === "money") return fmt.money(v, currency);
  if (format === "percent") return fmt.percent(v);
  return fmt.number(v);
}

/* ------------------------------------------------------------------ stats */

export type Stat = {
  label: React.ReactNode;
  value: unknown;
  hint?: React.ReactNode;
  tone?: Tone;
  format?: ValueFormat | "text";
  currency?: string;
};

const HINT_TONE: Record<Tone, string> = {
  success: "text-success",
  danger: "text-danger",
  warning: "text-warning",
  info: "text-info",
  neutral: "text-ink-3",
};

/** One number with its label (and an optional hint line). */
export function StatCard({ label, value, hint, tone = "neutral", format = "number", currency, className }: Stat & { className?: string }) {
  const text = format === "text" || typeof value === "string" ? fmt.text(value) : show(value, format as ValueFormat, currency);
  return (
    <div className={cn("flex min-w-0 flex-col gap-0.5 rounded-card border border-line bg-surface px-4 py-3.5", className)}>
      <span className="truncate text-2xl leading-tight font-medium tracking-[-0.02em] text-ink tabular-nums">{text}</span>
      <span className="truncate text-[13px] text-ink-3">{label}</span>
      {hint && <span className={cn("text-xs", HINT_TONE[tone])}>{hint}</span>}
    </div>
  );
}

/** A row of stat cards. */
export function StatRow({ stats, min = 160 }: { stats: Stat[]; min?: number }) {
  return (
    <Grid min={min} gap={12}>
      {(stats ?? []).map((s, i) => (
        <StatCard key={i} {...s} />
      ))}
    </Grid>
  );
}

/* ------------------------------------------------------------------ chart */

export type ChartProps = {
  type?: "bar" | "hbar" | "line" | "area" | "donut";
  /** [{ label, value }] (from aggregate / byMonth / countBy), or rows with `x` and `series` keys. */
  data: Point[] | Record<string, unknown>[];
  x?: string;
  series?: { key: string; label?: string }[];
  format?: ValueFormat;
  currency?: string;
  height?: number;
  title?: React.ReactNode;
  description?: React.ReactNode;
};

function ChartTooltip({
  active,
  payload,
  label,
  format,
  currency,
}: {
  active?: boolean;
  payload?: { name?: string; value?: unknown; color?: string; payload?: Record<string, unknown> }[];
  label?: unknown;
  format?: ValueFormat;
  currency?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[10px] border border-line bg-surface px-3 py-2 text-xs shadow-pop">
      {label !== undefined && label !== "" && <div className="mb-1 font-medium text-ink">{String(label)}</div>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block size-2 rounded-full" style={{ background: p.color }} />
          {payload.length > 1 && <span>{p.name}</span>}
          <span className="ml-auto font-medium text-ink tabular-nums">{show(p.value, format, currency)}</span>
        </div>
      ))}
    </div>
  );
}

function Donut({ data, format, currency, height }: { data: Point[]; format?: ValueFormat; currency?: string; height: number }) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const top = sorted.length > 5 ? [...sorted.slice(0, 4), { label: "Other", value: sorted.slice(4).reduce((s, p) => s + p.value, 0) }] : sorted;
  const total = top.reduce((s, p) => s + p.value, 0);
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div style={{ width: Math.min(height, 220), height: Math.min(height, 220) }} className="relative shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={top} dataKey="value" nameKey="label" innerRadius="62%" outerRadius="100%" paddingAngle={1.5} stroke="none" isAnimationActive={false}>
              {top.map((p, i) => (
                <Cell key={i} fill={p.label === "Other" && sorted.length > 5 ? OTHER : SERIES[i % 5]} />
              ))}
            </Pie>
            <RTooltip content={<ChartTooltip format={format} currency={currency} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="text-lg font-medium text-ink tabular-nums">{show(total, format, currency)}</div>
            <div className="text-[11px] text-ink-3">Total</div>
          </div>
        </div>
      </div>
      <ul className="m-0 flex min-w-[160px] flex-1 list-none flex-col gap-1.5 p-0">
        {top.map((p, i) => (
          <li key={i} className="flex items-center gap-2 text-[13px]">
            <span className="inline-block size-[7px] shrink-0 rounded-full" style={{ background: p.label === "Other" && sorted.length > 5 ? OTHER : SERIES[i % 5] }} />
            <span className="truncate text-ink-2">{p.label}</span>
            <span className="ml-auto font-medium text-ink tabular-nums">{show(p.value, format, currency)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A chart from points or rows. Flat fills, palette series colours, no gradients. */
export function Chart({ type = "bar", data, x = "label", series, format = "number", currency, height = 240, title, description }: ChartProps) {
  const rows = (data ?? []) as Record<string, unknown>[];
  const keys = (series?.length ? series : [{ key: "value", label: "Value" }]).slice(0, 5);
  let body: React.ReactNode;
  if (!rows.length) body = <EmptyState title="No data yet" description={null} className="py-8" />;
  else if (type === "donut") body = <Donut data={rows as Point[]} format={format} currency={currency} height={height} />;
  else {
    const common = { data: rows, margin: { top: 8, right: 8, bottom: 0, left: 0 } };
    const tickFmt = (v: unknown) => (format === "money" ? fmt.money(v, currency) : fmt.number(v, 1));
    const grid = <CartesianGrid vertical={false} stroke="var(--dmx-line-soft)" />;
    const tooltip = <RTooltip cursor={{ fill: "var(--dmx-surface-2)" }} content={<ChartTooltip format={format} currency={currency} />} />;
    const xAxis = <XAxis dataKey={x} tick={TICK} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={12} />;
    const whole = keys.every((k) => rows.every((r) => Number.isInteger(Number(r[k.key] ?? 0))));
    const yAxis = <YAxis tick={TICK} tickLine={false} axisLine={false} width={56} tickFormatter={tickFmt} allowDecimals={!whole} />;
    body = (
      <div style={{ height }} className="w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          {type === "line" ? (
            <LineChart {...common}>
              {grid}
              {xAxis}
              {yAxis}
              {tooltip}
              {keys.map((k, i) => (
                <Line key={k.key} type="monotone" dataKey={k.key} name={k.label ?? fmt.label(k.key)} stroke={SERIES[i]} strokeWidth={2} dot={rows.length <= 12 ? { r: 3, fill: SERIES[i], strokeWidth: 0 } : false} isAnimationActive={false} />
              ))}
            </LineChart>
          ) : type === "area" ? (
            <AreaChart {...common}>
              {grid}
              {xAxis}
              {yAxis}
              {tooltip}
              {keys.map((k, i) => (
                <Area key={k.key} type="monotone" dataKey={k.key} name={k.label ?? fmt.label(k.key)} stroke={SERIES[i]} strokeWidth={2} fill={SERIES[i]} fillOpacity={0.12} isAnimationActive={false} />
              ))}
            </AreaChart>
          ) : type === "hbar" ? (
            <BarChart {...common} layout="vertical">
              <CartesianGrid horizontal={false} stroke="var(--dmx-line-soft)" />
              <XAxis type="number" tick={TICK} tickLine={false} axisLine={false} tickFormatter={tickFmt} allowDecimals={!whole} />
              <YAxis type="category" dataKey={x} tick={TICK} tickLine={false} axisLine={false} width={112} />
              {tooltip}
              {keys.map((k, i) => (
                <Bar key={k.key} dataKey={k.key} name={k.label ?? fmt.label(k.key)} fill={SERIES[i]} radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive={false} />
              ))}
            </BarChart>
          ) : (
            <BarChart {...common}>
              {grid}
              {xAxis}
              {yAxis}
              {tooltip}
              {keys.map((k, i) => (
                <Bar key={k.key} dataKey={k.key} name={k.label ?? fmt.label(k.key)} fill={SERIES[i]} radius={[6, 6, 0, 0]} maxBarSize={40} isAnimationActive={false} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    );
  }
  if (!title && !description) return <>{body}</>;
  return (
    <Card title={title} description={description} className="gap-3 px-4 py-4">
      {body}
    </Card>
  );
}

/* ------------------------------------------------------------------ dashboard */

/** Stats on top, a grid of titled charts, then anything else (e.g. a DataTable). */
export function Dashboard({ stats, charts, children }: { stats?: Stat[]; charts?: ChartProps[]; children?: React.ReactNode }) {
  return (
    <Stack gap={16}>
      {!!stats?.length && <StatRow stats={stats} />}
      {!!charts?.length && (
        <Grid min={340} gap={12}>
          {charts.map((c, i) => (
            <Chart key={i} {...c} title={c.title ?? " "} />
          ))}
        </Grid>
      )}
      {children}
    </Stack>
  );
}
