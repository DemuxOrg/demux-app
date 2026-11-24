"use client";

/** One workspace over time: cost, matching emails per day, run history. */
import Link from "next/link";
import { use, useState } from "react";
import { EditsList, RunsTable } from "@/components/admin/RunsTable";
import { CHART_COLORS, TimeChart } from "@/components/admin/TimeChart";
import {
  Card,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  RangePicker,
  StatTile,
  Tiles,
  num,
  statusTone,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import { adminApi, type AdminRange } from "@/lib/api";

export default function AdminWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [days, setDays] = useState<AdminRange>(30);
  const { data, error, notFound } = useAdminData(`ws-${id}-${days}`, () =>
    adminApi.workspace(id, days),
  );

  if (notFound)
    return (
      <ErrorNote message="This workspace does not exist (or was deleted)." />
    );
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;
  const w = data.workspace;
  const cost = data.daily.reduce((s, d) => s + d.cost_usd, 0);
  const emails = data.daily.reduce((s, d) => s + d.emails, 0);

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            {w.name}
            <Pill tone={statusTone(w.status)}>{w.status}</Pill>
          </span>
        }
        note={
          <>
            Owner{" "}
            <Link
              href={`/admin/users/${w.user_id}`}
              className="font-medium text-ink hover:text-violet-ink hover:underline"
            >
              {data.owner_email}
            </Link>
          </>
        }
        right={<RangePicker value={days} onChange={setDays} />}
      />
      <Card title="Prompt">
        <p className="text-[15px] text-pretty text-ink">{w.prompt}</p>
      </Card>
      <Tiles>
        <StatTile
          label={`Cost, last ${days} days`}
          value={usd(cost)}
          sub={`${usd(w.cost_total)} all time`}
        />
        <StatTile
          label={`Emails processed, last ${days} days`}
          value={num(emails)}
          sub={`${num(w.emails_processed)} all time`}
        />
        <StatTile label="Records" value={num(w.record_count)} />
        <StatTile label="Runs in range" value={num(w.runs.length)} />
      </Tiles>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Cost per day">
          <TimeChart
            kind="bar"
            data={data.daily.map((d) => ({ date: d.date, cost: d.cost_usd }))}
            series={[{ key: "cost", label: "Cost", color: CHART_COLORS[0] }]}
            format={usd}
          />
        </Card>
        <Card
          title="Matching emails per day"
          note="New messages this workspace processed."
        >
          <TimeChart
            kind="bar"
            data={data.daily.map((d) => ({ date: d.date, emails: d.emails }))}
            series={[
              { key: "emails", label: "Emails", color: CHART_COLORS[3] },
            ]}
            format={num}
          />
        </Card>
      </div>
      <Card title="Runs" note={`In the last ${days} days.`}>
        <RunsTable runs={w.runs} />
      </Card>
      <Card title="Edit messages">
        <EditsList edits={w.edits} />
      </Card>
    </>
  );
}
