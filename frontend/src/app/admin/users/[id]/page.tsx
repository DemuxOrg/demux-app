"use client";

/** One user: who they are, what they asked for, how much mail they get, what they cost. */
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { use } from "react";
import { EditsList, RunsTable } from "@/components/admin/RunsTable";
import { CHART_COLORS, TimeChart } from "@/components/admin/TimeChart";
import {
  AccessPill,
  Card,
  Empty,
  ErrorNote,
  GmailPill,
  Loading,
  PageHeader,
  Pill,
  StatTile,
  Tiles,
  longDate,
  num,
  statusTone,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import { adminApi, timeAgo, type AdminWorkspace } from "@/lib/api";

function WorkspaceCard({ w }: { w: AdminWorkspace }) {
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          {w.name}
          <Pill tone={statusTone(w.status)}>{w.status}</Pill>
        </span>
      }
      note={`Created ${longDate(w.created_at)} · last sync ${w.last_synced_at ? timeAgo(w.last_synced_at) : "never"}`}
      right={
        <Link
          href={`/admin/workspaces/${w.id}`}
          className="group inline-flex h-9 items-center gap-1 rounded-full px-2 text-[13px] font-medium text-ink-2 hover:text-violet-ink"
        >
          Usage over time
          <ChevronRight size={14} aria-hidden className="dmx-nudge" />
        </Link>
      }
    >
      <blockquote className="mb-4 rounded-sm bg-surface-2 px-4 py-3 text-[15px] text-pretty text-ink">
        {w.prompt}
      </blockquote>
      <dl className="mb-4 flex flex-wrap gap-x-8 gap-y-2 text-[13px]">
        {[
          ["Records", num(w.record_count)],
          ["Emails processed", num(w.emails_processed)],
          ["Matching emails / day (7d)", num(w.emails_per_day)],
          ["Cost 7d", usd(w.cost_7d)],
          ["Cost 30d", usd(w.cost_30d)],
          ["Cost total", usd(w.cost_total)],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="text-ink-3">{k}</dt>
            <dd className="tabular text-[15px] font-medium text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <h3 className="mb-1 text-[13px] font-medium text-ink-2">
        Runs (latest {w.runs.length})
      </h3>
      <RunsTable runs={w.runs} />
      <h3 className="mt-5 mb-1 text-[13px] font-medium text-ink-2">
        Edit messages
      </h3>
      <EditsList edits={w.edits} />
    </Card>
  );
}

export default function AdminUserPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, error, notFound } = useAdminData(`user-${id}`, () =>
    adminApi.user(id),
  );

  if (notFound)
    return <ErrorNote message="This user does not exist (or was deleted)." />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;
  const u = data.user;
  const counted = data.mailbox_daily.filter((d) => d.count != null).length;

  return (
    <>
      <PageHeader
        title={u.email}
        note={
          <>
            {u.name && `${u.name} · `}Signed up {longDate(u.created_at)} · last
            active {u.last_active_at ? timeAgo(u.last_active_at) : "never"}
          </>
        }
        right={
          <span className="flex flex-wrap items-center gap-2">
            <AccessPill access={u.access} />
            <GmailPill
              connected={u.gmail_connected}
              needsReconnect={u.needs_reconnect}
            />
          </span>
        }
      />
      <Tiles>
        <StatTile label="Cost 7d" value={usd(u.cost_7d)} />
        <StatTile label="Cost 30d" value={usd(u.cost_30d)} />
        <StatTile label="Cost total" value={usd(u.cost_total)} />
        <StatTile label="Emails processed" value={num(u.emails_processed)} />
        <StatTile
          label="Emails received / day"
          value={
            u.emails_received_per_day == null
              ? "–"
              : num(u.emails_received_per_day)
          }
          sub="7-day average, whole inbox"
        />
      </Tiles>
      <Card
        title="Emails received per day"
        note="Whole inbox, counted from message ids only (last 30 finished days)."
      >
        {counted === 0 ? (
          <Empty>
            Not counted yet: the worker counts once an hour while Gmail is
            connected.
          </Empty>
        ) : (
          <TimeChart
            kind="bar"
            data={data.mailbox_daily.map((d) => ({
              date: d.date,
              count: d.count,
            }))}
            series={[
              {
                key: "count",
                label: "Emails received",
                color: CHART_COLORS[3],
              },
            ]}
            format={num}
          />
        )}
      </Card>
      {data.workspaces.length === 0 ? (
        <Card>
          <Empty>No workspaces.</Empty>
        </Card>
      ) : (
        data.workspaces.map((w) => <WorkspaceCard key={w.id} w={w} />)
      )}
    </>
  );
}
