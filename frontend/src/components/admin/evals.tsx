"use client";

/**
 * Shared bits of the eval pages (theme.md §7.14, §8 screen 6): part labels, score and
 * change formatting, the guardrail summary, and which earlier run a score compares to.
 */
import type { EvalParts, EvalRunRow } from "@/lib/api";
import { Pill, statusTone } from "./ui";

export const PARTS: { key: keyof EvalParts; label: string; note: string }[] = [
  {
    key: "retrieval",
    label: "Email recall",
    note: "Relevant emails that made it into a record",
  },
  {
    key: "coverage",
    label: "Request coverage",
    note: "Things the prompt asks for, in the data and on screen",
  },
  {
    key: "correctness",
    label: "Correctness",
    note: "Expected records and values",
  },
  {
    key: "clarification",
    label: "Clarification",
    note: "Asked when the prompt was vague, only then",
  },
];

export const score = (v: number | null | undefined) =>
  v == null ? "–" : v.toFixed(1);

export const shortHash = (v: string | null | undefined, n = 7) =>
  v ? v.slice(0, n) : "–";

/** The newest finished run before `run` (in a newest-first list) with the same suite. */
export function previousComparable(
  runs: EvalRunRow[],
  run: EvalRunRow,
): EvalRunRow | null {
  const i = runs.findIndex((r) => r.id === run.id);
  return (
    runs
      .slice(i + 1)
      .find(
        (r) =>
          r.status === "done" &&
          r.score != null &&
          r.suite_hash === run.suite_hash,
      ) ?? null
  );
}

/** The run before this one (any status) ran another suite: scores don't compare. */
export function suiteChanged(runs: EvalRunRow[], run: EvalRunRow): boolean {
  const i = runs.findIndex((r) => r.id === run.id);
  const before = runs.slice(i + 1).find((r) => r.status === "done");
  return !!before && !!run.suite_hash && before.suite_hash !== run.suite_hash;
}

export function Delta({
  now,
  before,
}: {
  now: number | null | undefined;
  before: number | null | undefined;
}) {
  if (now == null || before == null) return null;
  const d = now - before;
  if (Math.abs(d) < 0.05) return <span className="text-ink-3">no change</span>;
  return (
    <span className={d > 0 ? "text-success" : "text-danger"}>
      {d > 0 ? "▲" : "▼"} {Math.abs(d).toFixed(1)}
    </span>
  );
}

export function guardrailCount(run: EvalRunRow): {
  met: number;
  known: number;
} {
  const known = run.guardrails.filter((g) => g.met != null);
  return { met: known.filter((g) => g.met).length, known: known.length };
}

export function guardrailValue(key: string, v: number | null): string {
  if (v == null) return "n/a";
  if (key === "injection_resistance") return v >= 1 ? "pass" : "fail";
  return `${Math.round(v * 1000) / 10}%`;
}

export function EvalStatus({ run }: { run: EvalRunRow }) {
  const tone = run.status === "cancelled" ? "neutral" : statusTone(run.status);
  return <Pill tone={tone}>{run.status}</Pill>;
}

export function progressLabel(run: EvalRunRow): string {
  return `${run.progress_done} of ${run.progress_total} scenarios`;
}
