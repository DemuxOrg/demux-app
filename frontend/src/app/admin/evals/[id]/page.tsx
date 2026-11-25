"use client";

/**
 * One eval run (theme.md §8 screen 6): the score and its parts, the guardrails, then
 * every scenario as a collapsible card with its missed emails, asks, clarifying
 * questions and each step's checks. Fixture content only (synthetic mailboxes).
 */
import { Check, X } from "lucide-react";
import { use, useEffect, useMemo, useState, type ReactNode } from "react";
import { ButtonLink } from "@/components/ui/Button";
import {
  EvalStatus,
  PARTS,
  guardrailValue,
  progressLabel,
  score,
  shortHash,
} from "@/components/admin/evals";
import {
  Card,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  Segmented,
  StatTile,
  Tiles,
  dateTime,
  duration,
  num,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import { adminApi, type EvalScenarioResult } from "@/lib/api";

type Filter = "all" | "issues";

export default function AdminEvalRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, error, notFound, reload } = useAdminData(`eval-${id}`, () =>
    adminApi.evalRun(id),
  );
  const [filter, setFilter] = useState<Filter>("issues");
  const active = data?.status === "queued" || data?.status === "running";

  useEffect(() => {
    if (!active) return;
    const t = setInterval(reload, 4000);
    return () => clearInterval(t);
  }, [active, reload]);

  const shown = useMemo(
    () =>
      (data?.scenarios ?? []).filter((s) => filter === "all" || s.score < 100),
    [data, filter],
  );

  if (notFound) return <ErrorNote message="This eval run does not exist." />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;

  const took =
    data.started_at && data.finished_at
      ? (new Date(data.finished_at).getTime() -
          new Date(data.started_at).getTime()) /
        1000
      : null;

  return (
    <>
      <PageHeader
        title={`Eval run · ${dateTime(data.created_at)}`}
        note={
          <>
            Commit{" "}
            <span className="font-mono">{shortHash(data.commit, 10)}</span>
            {data.branch && ` (${data.branch})`} · agent{" "}
            <span className="font-mono">{shortHash(data.agent_hash)}</span> ·
            suite{" "}
            <span className="font-mono">{shortHash(data.suite_hash)}</span> ·{" "}
            {data.build_model} · {usd(data.cost_usd)}
            {took != null && ` · ${duration(took)}`}
          </>
        }
        right={
          <ButtonLink href="/admin/evals" variant="secondary">
            All evals
          </ButtonLink>
        }
      />
      {data.error && <ErrorNote message={data.error} />}
      {active && (
        <Card>
          <p className="flex items-center gap-3 text-sm text-ink-2">
            <EvalStatus run={data} />
            {progressLabel(data)} · {usd(data.cost_usd)} so far
          </p>
        </Card>
      )}
      {data.score != null && (
        <Tiles>
          <StatTile
            label="Demux score"
            value={score(data.score)}
            sub={
              data.spread != null
                ? `± ${score(data.spread)} over ${data.repeats} repeats`
                : `${data.repeats} repeat`
            }
          />
          {PARTS.map((p) => (
            <StatTile
              key={p.key}
              label={p.label}
              value={score(data.parts[p.key])}
              sub={p.note}
            />
          ))}
        </Tiles>
      )}
      {data.guardrails.length > 0 && (
        <Card
          title="Guardrails"
          note="Shown next to the score, never blended into it."
        >
          <ul className="flex flex-col">
            {data.guardrails.map((g) => (
              <li
                key={g.key}
                className="flex min-h-11 items-center justify-between gap-3 border-t border-line-soft py-2 first:border-t-0"
              >
                <span className="text-sm text-ink">{g.label}</span>
                <span className="flex items-center gap-2 text-[13px] text-ink-3">
                  <span className="tabular">
                    {guardrailValue(g.key, g.value)}
                    {g.key !== "injection_resistance" &&
                      ` (${g.op} ${guardrailValue(g.key, g.target)})`}
                  </span>
                  {g.met == null ? (
                    <Pill tone="neutral">n/a</Pill>
                  ) : g.met ? (
                    <Pill tone="success">met</Pill>
                  ) : (
                    <Pill tone="danger">missed</Pill>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {data.scenarios.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-ink">
            Scenarios ({num(data.scenarios.length)})
          </h2>
          <Segmented<Filter>
            label="Which scenarios"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "issues", label: "Below 100" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
      )}
      {data.scenarios.length > 0 && shown.length === 0 && (
        <Card>
          <Empty>Every scenario scored 100.</Empty>
        </Card>
      )}
      {shown.map((s) => (
        <Scenario key={`${s.id}-${s.repeat}`} s={s} repeats={data.repeats} />
      ))}
      <p className="text-[13px] text-ink-on-sky">
        Details come from the synthetic test mailboxes in
        backend/eval/agent/scenarios, never from a user&apos;s inbox.
      </p>
    </>
  );
}

function Mark({ ok }: { ok: boolean | null | undefined }) {
  if (ok == null) return <span className="w-4 text-ink-3">–</span>;
  return ok ? (
    <Check size={16} aria-label="pass" className="shrink-0 text-success" />
  ) : (
    <X size={16} aria-label="fail" className="shrink-0 text-danger" />
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line-soft pt-4">
      <h3 className="mb-2 text-[13px] font-medium text-ink-3">{title}</h3>
      {children}
    </section>
  );
}

function Scenario({ s, repeats }: { s: EvalScenarioResult; repeats: number }) {
  const missed = s.retrieval?.groups.filter((g) => !g.recalled) ?? [];
  return (
    <details className="group min-w-0 rounded-lg bg-surface shadow-glass">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 rounded-lg px-[22px] py-4 focus-visible:ring-[3px] focus-visible:ring-violet/25">
        <span className="min-w-0">
          <span className="block text-[15px] font-semibold text-ink">
            {s.id}
            {repeats > 1 && (
              <span className="font-normal text-ink-3">
                {" "}
                · repeat {s.repeat}
              </span>
            )}
          </span>
          <span className="block truncate text-[13px] text-ink-3">
            {s.prompt}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-4 text-[13px] text-ink-3">
          {PARTS.map((p) =>
            s.parts[p.key] == null ? null : (
              <span key={p.key} className="tabular">
                {p.label} {score(s.parts[p.key])}
              </span>
            ),
          )}
          <span
            className={`tabular text-[22px] font-medium ${s.score < 100 ? "text-ink" : "text-ink-3"}`}
          >
            {score(s.score)}
          </span>
        </span>
      </summary>
      <div className="flex flex-col gap-4 px-[22px] pb-5">
        {s.retrieval && (
          <Section
            title={`Email recall: ${s.retrieval.recalled} of ${s.retrieval.total} found · ${s.retrieval.cited_threads} threads cited, ${s.retrieval.cited_relevant} of them relevant`}
          >
            <ul className="flex flex-col gap-1 text-sm">
              {[...missed, ...s.retrieval.groups.filter((g) => g.recalled)].map(
                (g) => (
                  <li key={g.label} className="flex items-center gap-2">
                    <Mark ok={g.recalled} />
                    <span className={g.recalled ? "text-ink-3" : "text-danger"}>
                      {g.label}
                    </span>
                    <span className="font-mono text-xs text-ink-3">
                      {g.thread_ids.length} thread
                      {g.thread_ids.length > 1 && "s"}
                    </span>
                  </li>
                ),
              )}
            </ul>
          </Section>
        )}
        {s.asks.length > 0 && (
          <Section title="Request coverage: each thing the prompt asks for">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="text-[13px] text-ink-3">
                    <th scope="col" className="pb-1 text-left font-medium">
                      Ask
                    </th>
                    <th scope="col" className="pb-1 text-left font-medium">
                      Step
                    </th>
                    <th scope="col" className="pb-1 text-left font-medium">
                      In data
                    </th>
                    <th scope="col" className="pb-1 text-left font-medium">
                      On screen
                    </th>
                    <th scope="col" className="pb-1 text-left font-medium">
                      Detail
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {s.asks.map((a) => (
                    <tr
                      key={`${a.step}-${a.ask}`}
                      className="h-9 border-t border-line-soft"
                    >
                      <td
                        className={`pr-4 ${a.score < 1 ? "text-ink" : "text-ink-3"}`}
                      >
                        {a.ask}
                      </td>
                      <td className="pr-4 text-ink-3">{a.step}</td>
                      <td className="pr-4">
                        <Mark ok={a.in_data} />
                      </td>
                      <td className="pr-4">
                        <Mark ok={a.in_app} />
                      </td>
                      <td className="text-[13px] text-ink-3">{a.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}
        {s.clarify && (
          <Section
            title={`Clarification: ${s.clarify.expected ? "the prompt is vague, the build should ask" : "the prompt is clear, the build should not ask"}`}
          >
            {s.clarify.questions.length === 0 ? (
              <p className="flex items-center gap-2 text-sm">
                <Mark ok={!s.clarify.expected} />
                <span
                  className={s.clarify.expected ? "text-danger" : "text-ink-3"}
                >
                  No question asked.
                </span>
              </p>
            ) : (
              <ul className="flex flex-col gap-3 text-sm">
                {!s.clarify.expected && (
                  <li className="flex items-center gap-2 text-danger">
                    <Mark ok={false} /> Asked on a clear prompt.
                  </li>
                )}
                {s.clarify.expected && (
                  <li className="flex items-center gap-2">
                    <Mark ok={!!s.clarify.on_topic} />
                    <span
                      className={
                        s.clarify.on_topic ? "text-ink-3" : "text-danger"
                      }
                    >
                      {s.clarify.on_topic
                        ? "A question names the real ambiguity."
                        : "No question names the real ambiguity."}
                    </span>
                  </li>
                )}
                {s.clarify.questions.map((q) => (
                  <li
                    key={q.question}
                    className="rounded-sm bg-surface-2 px-3 py-2"
                  >
                    <p className="text-ink">{q.question}</p>
                    <p className="mt-1 flex flex-wrap gap-1.5">
                      {q.options.map((o) => (
                        <span
                          key={o}
                          className={`rounded-[6px] px-2 py-0.5 text-[13px] ${
                            o === q.answer
                              ? "bg-violet-soft text-violet-ink"
                              : "bg-tag text-ink-2"
                          }`}
                        >
                          {o}
                        </span>
                      ))}
                    </p>
                    <p className="mt-1 text-[13px] text-ink-3">
                      {q.answer
                        ? "Scripted user picked the highlighted option."
                        : "No option matched the scripted answer: the recommended one was used."}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        )}
        {s.steps.map((st) => (
          <Section
            key={st.name}
            title={`${st.name} (${st.kind}) · ${num(st.record_count)} records · ${usd(st.cost_usd)} · ${duration(st.latency_s)}${st.app_renders ? "" : " · app did not render"}`}
          >
            {st.error && <p className="mb-2 text-sm text-danger">{st.error}</p>}
            {st.checks.length === 0 ? (
              <p className="text-[13px] text-ink-3">No checks on this step.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {st.checks.map((c, i) => (
                  <li
                    key={i}
                    className="flex min-w-0 items-start gap-2 text-[13px]"
                  >
                    <span className="pt-0.5">
                      <Mark ok={c.passed} />
                    </span>
                    <span className="min-w-0">
                      <code
                        className={`break-words font-mono text-xs ${c.passed ? "text-ink-3" : "text-ink"}`}
                      >
                        {c.expected}
                      </code>
                      {c.detail && (
                        <span
                          className={`block ${c.passed ? "text-ink-3" : "text-danger"}`}
                        >
                          {c.detail}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        ))}
      </div>
    </details>
  );
}
