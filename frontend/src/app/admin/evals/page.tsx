"use client";

/**
 * Agent evals (theme.md §7.14, §8 screen 6): run the scenario suite against the real
 * model on synthetic mailboxes, see the Demux score of the latest run and its history by
 * date and commit. Each run opens its full report.
 */
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/Button";
import {
  Delta,
  EvalStatus,
  PARTS,
  guardrailCount,
  previousComparable,
  progressLabel,
  score,
  shortHash,
  suiteChanged,
} from "@/components/admin/evals";
import { CHART_COLORS } from "@/components/admin/TimeChart";
import {
  Card,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  StatTile,
  Tiles,
  dateTime,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import {
  ApiError,
  adminApi,
  handleAuthError,
  type EvalRunRow,
  type EvalsState,
} from "@/lib/api";

const REPEATS = [1, 2, 3];
const GRID = "#edf1f6";
const AXIS = "#5b6b80";

function message(e: unknown): string {
  return e instanceof ApiError || e instanceof Error
    ? e.message
    : "Something went wrong.";
}

export default function AdminEvalsPage() {
  const { data, error, reload } = useAdminData("evals", adminApi.evals);
  const active = data?.runs.find(
    (r) => r.status === "queued" || r.status === "running",
  );

  // Poll while a run is queued or running.
  useEffect(() => {
    if (!active) return;
    const t = setInterval(reload, 4000);
    return () => clearInterval(t);
  }, [active, reload]);

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;

  const latest = data.runs.find((r) => r.status === "done" && r.score != null);
  const before = latest ? previousComparable(data.runs, latest) : null;

  return (
    <>
      <PageHeader
        title="Evals"
        note="Runs every scenario through a real build, sync and edit on synthetic mailboxes, then scores it. Costs real model spend."
      />
      <RunCard
        data={data}
        active={active ?? null}
        latest={latest ?? null}
        reload={reload}
      />
      {latest && (
        <Tiles>
          <StatTile
            label="Demux score"
            value={score(latest.score)}
            sub={
              <>
                {latest.spread != null && `± ${score(latest.spread)} · `}
                {before ? (
                  <Delta now={latest.score} before={before.score} />
                ) : (
                  "first run of this suite"
                )}
              </>
            }
          />
          {PARTS.map((p) => (
            <StatTile
              key={p.key}
              label={p.label}
              value={score(latest.parts[p.key])}
              sub={
                before ? (
                  <Delta
                    now={latest.parts[p.key]}
                    before={before.parts[p.key]}
                  />
                ) : (
                  p.note
                )
              }
            />
          ))}
        </Tiles>
      )}
      <ScoreChart runs={data.runs} />
      <History runs={data.runs} />
      <p className="text-[13px] text-ink-on-sky">
        Details come from the synthetic test mailboxes in
        backend/eval/agent/scenarios, never from a user&apos;s inbox.
      </p>
    </>
  );
}

function RunCard({
  data,
  active,
  latest,
  reload,
}: {
  data: EvalsState;
  active: EvalRunRow | null;
  latest: EvalRunRow | null;
  reload: () => void;
}) {
  const all = data.scenarios.map((s) => s.id);
  const [picked, setPicked] = useState<string[]>(all);
  const [repeats, setRepeats] = useState(1);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const estimate = useMemo(() => {
    if (!latest || !latest.progress_total) return null;
    return (latest.cost_usd / latest.progress_total) * picked.length * repeats;
  }, [latest, picked.length, repeats]);

  function toggle(id: string) {
    setPicked((p) =>
      p.includes(id)
        ? p.filter((x) => x !== id)
        : all.filter((x) => x === id || p.includes(x)),
    );
  }

  async function run() {
    setBusy(true);
    setFormError(null);
    try {
      await adminApi.createEval(
        repeats,
        picked.length === all.length ? [] : picked,
      );
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setFormError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!active) return;
    setBusy(true);
    try {
      await adminApi.cancelEval(active.id);
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setFormError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Run the eval suite"
      note={`Uses ${data.build_model}. Scores compare between runs of the same suite.`}
    >
      <fieldset disabled={!!active} className="flex min-w-0 flex-col gap-4">
        <legend className="sr-only">Scenarios</legend>
        <div className="flex flex-wrap gap-2">
          {data.scenarios.map((s) => {
            const on = picked.includes(s.id);
            return (
              <button
                key={s.id}
                type="button"
                aria-pressed={on}
                title={s.prompt}
                onClick={() => toggle(s.id)}
                className={`inline-flex h-9 max-w-full min-w-0 items-center gap-2 rounded-full border px-3.5 text-sm font-medium disabled:opacity-60 ${
                  on
                    ? "border-violet-line bg-violet-soft text-violet-ink"
                    : "border-chip-line bg-surface-3 text-ink-3 hover:text-ink-2"
                }`}
              >
                <span className="min-w-0 truncate">{s.id}</span>
                {s.vague && (
                  <span className="shrink-0 rounded-[6px] bg-white/70 px-1.5 text-xs text-ink-2">
                    asks
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4 text-[13px] text-ink-2">
            <label className="flex items-center gap-2 font-medium">
              Repeats
              <select
                value={repeats}
                onChange={(e) => setRepeats(Number(e.target.value))}
                className="h-10 rounded-full border border-line bg-surface px-3 text-sm text-ink focus:border-violet-line focus:outline-none"
              >
                {REPEATS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <span>
              {picked.length} of {all.length} scenarios
              {estimate != null &&
                ` · about ${usd(estimate)}, from the last run`}
            </span>
          </div>
          {active ? (
            <span className="flex items-center gap-3 text-[13px] text-ink-2">
              <EvalStatus run={active} />
              {progressLabel(active)}
              <Button variant="quiet" loading={busy} onClick={cancel}>
                Cancel
              </Button>
            </span>
          ) : (
            <Button
              type="button"
              loading={busy}
              disabled={picked.length === 0}
              onClick={run}
            >
              Run evals
            </Button>
          )}
        </div>
        {repeats > 1 && !active && (
          <p className="text-[13px] text-ink-3">
            Repeats give the spread: a change smaller than it is noise.
          </p>
        )}
        {formError && <p className="text-sm text-danger">{formError}</p>}
      </fieldset>
    </Card>
  );
}

type Point = {
  i: number;
  when: string;
  score: number;
  spread: number | null;
  commit: string;
  suite: string;
};

/** Dates on the x axis, or times when every run is on the same day. */
function tick(points: Point[], i: number): string {
  const d = new Date(points[i]?.when ?? 0);
  const days = new Set(points.map((p) => new Date(p.when).toDateString()));
  return days.size === 1
    ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function ScoreChart({ runs }: { runs: EvalRunRow[] }) {
  const [table, setTable] = useState(false);
  const points: Point[] = useMemo(
    () =>
      runs
        .filter((r) => r.status === "done" && r.score != null)
        .reverse()
        .map((r, i) => ({
          i,
          when: r.created_at,
          score: r.score as number,
          spread: r.spread,
          commit: shortHash(r.commit),
          suite: shortHash(r.suite_hash),
        })),
    [runs],
  );
  if (points.length < 2) return null;
  const changes = points.filter(
    (p, i) => i > 0 && p.suite !== points[i - 1].suite,
  );

  return (
    <Card
      title="Demux score over runs"
      note="One point per finished run. A dashed line marks a suite change: scores before it don't compare."
    >
      <div style={{ height: 220 }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            margin={{ top: 8, right: 4, bottom: 0, left: 0 }}
            accessibilityLayer
          >
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="i"
              tickFormatter={(i: number) => tick(points, i)}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: AXIS }}
              minTickGap={16}
            />
            <YAxis
              domain={[0, 100]}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: AXIS }}
              width={40}
            />
            {changes.map((p) => (
              <ReferenceLine
                key={p.i}
                x={p.i}
                stroke={AXIS}
                strokeDasharray="3 3"
              />
            ))}
            <Tooltip
              cursor={{ stroke: GRID }}
              content={({ active, payload }) => {
                const p =
                  active && (payload?.[0]?.payload as Point | undefined);
                if (!p) return null;
                return (
                  <div className="min-w-[160px] rounded-sm border border-line bg-surface px-3 py-2.5 text-[13px] shadow-glass">
                    <p className="font-semibold text-ink">{dateTime(p.when)}</p>
                    <p className="tabular mt-1 text-ink">
                      {score(p.score)}
                      {p.spread != null && ` ± ${score(p.spread)}`}
                    </p>
                    <p className="text-ink-3">
                      commit {p.commit} · suite {p.suite}
                    </p>
                  </div>
                );
              }}
            />
            <Line
              dataKey="score"
              name="Demux score"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              dot={{ r: 3, fill: CHART_COLORS[0], strokeWidth: 0 }}
              activeDot={{ r: 4, stroke: "#ffffff", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex justify-end">
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
                <th className="px-3 py-2 text-left font-medium">Run</th>
                <th className="px-3 py-2 text-left font-medium">Commit</th>
                <th className="px-3 py-2 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p) => (
                <tr key={p.i} className="border-t border-line-soft">
                  <td className="px-3 py-1.5 text-ink-2">{dateTime(p.when)}</td>
                  <td className="px-3 py-1.5 font-mono text-ink-2">
                    {p.commit}
                  </td>
                  <td className="tabular px-3 py-1.5 text-right text-ink">
                    {score(p.score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function History({ runs }: { runs: EvalRunRow[] }) {
  return (
    <Card
      title="History"
      note="Newest first. Open a run for every scenario, step and check."
    >
      {runs.length === 0 ? (
        <Empty>No eval has run yet.</Empty>
      ) : (
        <div className="-mx-[22px] overflow-x-auto px-[22px]">
          <table className="w-full min-w-[1080px] text-sm">
            <thead>
              <tr className="text-[13px] text-ink-3">
                <th scope="col" className="pb-2 text-left font-medium">
                  When
                </th>
                <th scope="col" className="pb-2 text-left font-medium">
                  Commit
                </th>
                <th scope="col" className="pb-2 text-right font-medium">
                  Score
                </th>
                {PARTS.map((p) => (
                  <th
                    key={p.key}
                    scope="col"
                    className="pb-2 text-right font-medium"
                  >
                    {p.label}
                  </th>
                ))}
                <th scope="col" className="pb-2 text-right font-medium">
                  Guardrails
                </th>
                <th scope="col" className="pb-2 text-right font-medium">
                  Cost
                </th>
                <th scope="col" className="pb-2 pl-4 text-left font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const g = guardrailCount(r);
                return (
                  <tr
                    key={r.id}
                    className="h-11 border-t border-line-soft align-middle"
                  >
                    <td className="py-2 pr-4">
                      <Link
                        href={`/admin/evals/${r.id}`}
                        className="font-medium whitespace-nowrap text-ink hover:text-violet-ink hover:underline"
                      >
                        {dateTime(r.created_at)}
                      </Link>
                      <span className="block text-[13px] text-ink-3">
                        {r.scenario_ids.length
                          ? `${r.scenario_ids.length} scenarios`
                          : "all scenarios"}
                        {r.repeats > 1 && ` × ${r.repeats}`}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      <span className="font-mono text-[13px] text-ink">
                        {shortHash(r.commit)}
                      </span>
                      {r.branch && (
                        <span className="ml-2 text-[13px] text-ink-3">
                          {r.branch}
                        </span>
                      )}
                      <span className="block font-mono text-xs text-ink-3">
                        agent {shortHash(r.agent_hash)} · suite{" "}
                        {shortHash(r.suite_hash)}
                        {suiteChanged(runs, r) && (
                          <span className="ml-2 font-sans">
                            <Pill tone="warning">suite changed</Pill>
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="tabular pr-4 text-right font-medium text-ink">
                      {score(r.score)}
                      {r.spread != null && (
                        <span className="font-normal text-ink-3">
                          {" "}
                          ± {score(r.spread)}
                        </span>
                      )}
                    </td>
                    {PARTS.map((p) => (
                      <td
                        key={p.key}
                        className="tabular pr-4 text-right text-ink-2"
                      >
                        {score(r.parts[p.key])}
                      </td>
                    ))}
                    <td
                      className={`tabular pr-4 text-right ${g.known && g.met < g.known ? "text-danger" : "text-ink-2"}`}
                    >
                      {g.known ? `${g.met} of ${g.known}` : "–"}
                    </td>
                    <td className="tabular pr-4 text-right text-ink-2">
                      {usd(r.cost_usd)}
                    </td>
                    <td className="pl-4">
                      <span className="flex items-center gap-2">
                        <EvalStatus run={r} />
                        {(r.status === "running" || r.status === "queued") && (
                          <span className="text-[13px] whitespace-nowrap text-ink-3">
                            {progressLabel(r)}
                          </span>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
