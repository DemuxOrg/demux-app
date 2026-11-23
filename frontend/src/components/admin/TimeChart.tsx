"use client";

/**
 * Daily chart for the admin pages (theme.md §7.14): bars (optionally stacked) or lines
 * over UTC days, one y-axis, a hover tooltip, a legend for two or more series, and a
 * "Show table" toggle with the exact values (also the relief for low-contrast hues).
 */
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { day } from "./ui";

/** Series colours in fixed order (globals.css `--color-chart-*`, theme.md §7.14). */
export const CHART_COLORS = [
  "#6a3df0",
  "#eb6834",
  "#1baf7a",
  "#2a78d6",
  "#d63a7c",
] as const;
export const DANGER = "#a8321f";
const GRID = "#edf1f6";
const AXIS = "#5b6b80";

export type Series = { key: string; label: string; color: string };
export type Row = { date: string } & Record<string, number | string | null>;

function ChartTooltip({
  active,
  payload,
  label,
  series,
  format,
  footer,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
  label?: unknown;
  series: Series[];
  format: (v: number) => string;
  footer?: (row: Row) => string | null;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Row;
  const note = footer?.(row);
  return (
    <div className="min-w-[160px] rounded-sm border border-line bg-surface px-3 py-2.5 text-[13px] shadow-glass">
      <p className="mb-1.5 font-semibold text-ink">{day(String(label))}</p>
      <ul className="flex flex-col gap-1">
        {[...series].reverse().map((s) => (
          <li key={s.key} className="flex items-center gap-2 text-ink-2">
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: s.color }}
            />
            <span className="flex-1">{s.label}</span>
            <span className="tabular font-medium text-ink">
              {row[s.key] == null ? "–" : format(Number(row[s.key]))}
            </span>
          </li>
        ))}
      </ul>
      {note && <p className="mt-1.5 text-ink-3">{note}</p>}
    </div>
  );
}

export function TimeChart({
  kind,
  data,
  series,
  format,
  axisFormat,
  stacked = false,
  footer,
  height = 220,
}: {
  kind: "bar" | "line";
  data: Row[];
  series: Series[];
  format: (v: number) => string;
  axisFormat?: (v: number) => string;
  stacked?: boolean;
  footer?: (row: Row) => string | null;
  height?: number;
}) {
  const [table, setTable] = useState(false);
  const many = data.length > 45;
  const common = {
    data,
    margin: { top: 8, right: 4, bottom: 0, left: 0 },
    accessibilityLayer: true,
  };
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke={GRID} />
      <XAxis
        dataKey="date"
        tickFormatter={day}
        tickLine={false}
        axisLine={false}
        tick={{ fontSize: 12, fill: AXIS }}
        minTickGap={many ? 28 : 16}
      />
      <YAxis
        tickFormatter={axisFormat ?? format}
        tickLine={false}
        axisLine={false}
        tick={{ fontSize: 12, fill: AXIS }}
        width={56}
        allowDecimals
      />
      <Tooltip
        cursor={{ fill: "rgba(12,26,46,.04)", stroke: GRID }}
        content={(props) => (
          <ChartTooltip
            {...props}
            series={series}
            format={format}
            footer={footer}
          />
        )}
      />
    </>
  );

  return (
    <div>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          {kind === "bar" ? (
            <BarChart {...common} barCategoryGap={many ? 1 : "20%"}>
              {axes}
              {series.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stackId={stacked ? "a" : undefined}
                  fill={s.color}
                  stroke="#ffffff"
                  strokeWidth={stacked ? 1 : 0}
                  radius={
                    !stacked || i === series.length - 1 ? [4, 4, 0, 0] : 0
                  }
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          ) : (
            <LineChart {...common}>
              {axes}
              {series.map((s) => (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, stroke: "#ffffff", strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        {series.length > 1 ? (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-2">
            {series.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="size-2.5 rounded-full"
                  style={{ background: s.color }}
                />
                {s.label}
              </li>
            ))}
          </ul>
        ) : (
          <span />
        )}
        <button
          type="button"
          aria-expanded={table}
          onClick={() => setTable((t) => !t)}
          className="h-8 rounded-full px-2 text-[13px] font-medium text-ink-2 hover:text-violet-ink focus-visible:ring-[3px] focus-visible:ring-violet/25"
        >
          {table ? "Hide table" : "Show table"}
        </button>
      </div>
      {table && (
        <div className="mt-2 max-h-72 overflow-auto rounded-sm border border-line-soft">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-surface-2 text-ink-3">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Day</th>
                {series.map((s) => (
                  <th key={s.key} className="px-3 py-2 text-right font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...data].reverse().map((row) => (
                <tr key={row.date} className="border-t border-line-soft">
                  <td className="px-3 py-1.5 text-ink-2">{day(row.date)}</td>
                  {series.map((s) => (
                    <td
                      key={s.key}
                      className="tabular px-3 py-1.5 text-right text-ink"
                    >
                      {row[s.key] == null ? "–" : format(Number(row[s.key]))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Long rows ({date, key, value}) to one wide row per day, with every series present. */
export function widen(
  days: string[],
  rows: { date: string; key: string; value: number }[],
  keys: string[],
  fold: (key: string) => string = (k) => k,
): Row[] {
  const byDay = new Map<string, Row>(
    days.map((d) => [
      d,
      { date: d, ...Object.fromEntries(keys.map((k) => [k, 0])) },
    ]),
  );
  for (const r of rows) {
    const row = byDay.get(r.date);
    const k = fold(r.key);
    if (row && k in row) row[k] = Number(row[k] ?? 0) + r.value;
  }
  return days.map((d) => byDay.get(d)!);
}
