"use client";

/** Admin overview (theme.md §8, screen 6): who used Demux, and what it cost, per day. */
import { useMemo, useState } from "react";
import {
  Card,
  ErrorNote,
  Loading,
  PageHeader,
  RangePicker,
  Segmented,
  StatTile,
  Tiles,
  compact,
  num,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import {
  CHART_COLORS,
  DANGER,
  TimeChart,
  widen,
  type Series,
} from "@/components/admin/TimeChart";
import { adminApi, type AdminOverview, type AdminRange } from "@/lib/api";

const PHASES: Series[] = [
  { key: "design", label: "Design", color: CHART_COLORS[0] },
  { key: "batch", label: "Reading emails", color: CHART_COLORS[1] },
  { key: "app", label: "App", color: CHART_COLORS[2] },
  { key: "edit", label: "Edit", color: CHART_COLORS[3] },
  { key: "seed", label: "Demo inbox", color: CHART_COLORS[4] },
];
const OTHER = "Other models";

/** Models in a stable (alphabetical) order: the first four get a slot, the rest fold. */
function modelSeries(o: AdminOverview): {
  series: Series[];
  fold: (k: string) => string;
} {
  const models = [...new Set(o.cost_by_model.map((r) => r.key))].sort();
  const named = models.length > 5 ? models.slice(0, 4) : models;
  const series = named.map((m, i) => ({
    key: m,
    label: m,
    color: CHART_COLORS[i],
  }));
  if (models.length > named.length)
    series.push({ key: OTHER, label: OTHER, color: CHART_COLORS[4] });
  return { series, fold: (k) => (named.includes(k) ? k : OTHER) };
}

function Charts({ o }: { o: AdminOverview }) {
  const [split, setSplit] = useState<"phase" | "model">("phase");
  const days = useMemo(() => o.tokens.map((t) => t.date), [o]);

  const cost = useMemo(() => {
    if (split === "phase") {
      const rows = o.cost_by_phase.map((r) => ({
        date: r.date,
        key: r.key,
        value: r.cost_usd,
      }));
      return {
        series: PHASES,
        data: widen(
          days,
          rows,
          PHASES.map((p) => p.key),
        ),
      };
    }
    const { series, fold } = modelSeries(o);
    const rows = o.cost_by_model.map((r) => ({
      date: r.date,
      key: r.key,
      value: r.cost_usd,
    }));
    return {
      series,
      data: widen(
        days,
        rows,
        series.map((s) => s.key),
        fold,
      ),
    };
  }, [o, split, days]);

  const tokens = o.tokens.map((t) => ({
    date: t.date,
    input: t.input_tokens,
    output: t.output_tokens,
  }));
  const perUser = o.cost_per_user.map((d) => ({
    date: d.date,
    p50: d.active_users ? d.p50_usd : null,
    p95: d.active_users ? d.p95_usd : null,
    users: d.active_users,
  }));
  const failures = o.failures.map((d) => ({
    date: d.date,
    rate: d.finished ? (100 * d.failed) / d.finished : null,
    failed: d.failed,
    finished: d.finished,
  }));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Daily cost"
        note="Every LLM call, by the day it was made (UTC)."
        right={
          <Segmented
            label="Split daily cost"
            value={split}
            onChange={setSplit}
            onWhite
            options={[
              { value: "phase", label: "By phase" },
              { value: "model", label: "By model" },
            ]}
          />
        }
      >
        <TimeChart
          kind="bar"
          stacked
          data={cost.data}
          series={cost.series}
          format={usd}
        />
      </Card>
      <Card
        title="Tokens in and out"
        note="Prompt tokens sent vs tokens generated."
      >
        <TimeChart
          kind="line"
          data={tokens}
          series={[
            { key: "input", label: "Tokens in", color: CHART_COLORS[0] },
            { key: "output", label: "Tokens out", color: CHART_COLORS[1] },
          ]}
          format={num}
          axisFormat={compact}
        />
      </Card>
      <Card
        title="Cost per active user"
        note="Per day, across users with LLM usage that day (demo inbox excluded)."
      >
        <TimeChart
          kind="line"
          data={perUser}
          series={[
            { key: "p50", label: "Median (p50)", color: CHART_COLORS[0] },
            { key: "p95", label: "p95", color: CHART_COLORS[1] },
          ]}
          format={usd}
          footer={(r) =>
            `${r.users} active ${r.users === 1 ? "user" : "users"}`
          }
        />
      </Card>
      <Card
        title="Run failure rate"
        note="Failed runs as a share of finished runs."
      >
        <TimeChart
          kind="bar"
          data={failures}
          series={[{ key: "rate", label: "Failure rate", color: DANGER }]}
          format={(v) => `${v.toFixed(1)}%`}
          axisFormat={(v) => `${Math.round(v)}%`}
          footer={(r) =>
            r.finished ? `${r.failed} of ${r.finished} runs failed` : "No runs"
          }
        />
      </Card>
    </div>
  );
}

export default function AdminOverviewPage() {
  const [days, setDays] = useState<AdminRange>(30);
  const {
    data: o,
    loading,
    error,
  } = useAdminData(`overview-${days}`, () => adminApi.overview(days));

  return (
    <>
      <PageHeader
        title="Usage"
        note={
          o
            ? `${o.start} to ${o.end} (UTC)${loading ? " · updating…" : ""}`
            : undefined
        }
        right={<RangePicker value={days} onChange={setDays} />}
      />
      {error && <ErrorNote message={error} />}
      {!o ? (
        !error && <Loading />
      ) : (
        <>
          <Tiles>
            <StatTile
              label="Active users"
              value={num(o.active_users)}
              sub={`of ${num(o.total_users)} accounts`}
            />
            <StatTile
              label="Workspaces"
              value={num(o.workspaces)}
              sub={`${num(o.new_workspaces)} new`}
            />
            <StatTile
              label="Builds · syncs · edits"
              value={`${num(o.builds)} · ${num(o.syncs)} · ${num(o.edits)}`}
              sub={`${num(o.failed_runs)} failed of ${num(o.finished_runs)}`}
            />
            <StatTile
              label="Tokens in"
              value={compact(o.input_tokens)}
              sub={num(o.input_tokens)}
            />
            <StatTile
              label="Tokens out"
              value={compact(o.output_tokens)}
              sub={num(o.output_tokens)}
            />
            <StatTile
              label="Cost"
              value={usd(o.cost_usd)}
              sub={
                o.active_users
                  ? `${usd(o.cost_usd / o.active_users)} per active user`
                  : undefined
              }
            />
          </Tiles>
          <Charts o={o} />
          <p className="text-[13px] text-ink-on-sky">
            Syncs that found no new email are not kept, so they are not counted.
          </p>
        </>
      )}
    </>
  );
}
