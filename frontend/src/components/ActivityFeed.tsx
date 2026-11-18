/**
 * Activity (theme.md §7.9): record changes grouped by run, newest first. Each group has
 * its time (the newest gets a violet dot); each change shows the record title, then
 * `from` → `to` pills for changed fields (or one sentence), then a link to the email.
 */
import { ArrowRight, Mail, Undo2 } from "lucide-react";
import type { ChangeRead, RunRead } from "@/lib/api";

const THREAD_ID = /^[0-9a-f]{8,32}$/;
const RUN_KIND: Record<string, string> = {
  build: "Build",
  sync: "Sync",
  edit: "Your change",
};

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Status-like values get the matching soft pill; anything else stays neutral. */
function tone(value: string): string {
  const v = value.toLowerCase();
  if (
    /\b(paid|approved|delivered|done|complete|completed|accepted|confirmed|received|offer)\b/.test(
      v,
    )
  )
    return "bg-success-bg text-success";
  if (/\b(overdue|rejected|failed|cancell?ed|declined|lost)\b/.test(v))
    return "bg-danger-bg text-danger";
  if (/\b(delayed|waiting|pending|on hold|late)\b/.test(v))
    return "bg-warning-bg text-warning";
  if (
    /\b(in transit|shipped|sent|scheduled|interview|in progress|booked)\b/.test(
      v,
    )
  )
    return "bg-info-bg text-info";
  return "bg-neutral-bg text-neutral";
}

function Pill({ value, status = false }: { value: string; status?: boolean }) {
  return (
    <span
      className={`inline-flex h-[22px] max-w-[150px] items-center truncate rounded-full px-2 text-xs font-medium ${
        status ? tone(value) : "bg-neutral-bg text-neutral"
      }`}
      title={value}
    >
      {value}
    </span>
  );
}

function title(after: ChangeRead["after"], before: ChangeRead["before"]) {
  const rec = (after ?? before ?? {}) as Record<string, unknown>;
  const keys = Object.keys(rec).filter((k) => !k.startsWith("_") && rec[k]);
  const key =
    keys.find((k) => /name|title|subject|label/.test(k)) ??
    keys.find((k) =>
      /client|customer|company|vendor|supplier|merchant|store|sender|employer|item|product|description/.test(
        k,
      ),
    );
  return key ? fmt(rec[key]) : null;
}

function ChangeItem({ c }: { c: ChangeRead }) {
  if (c.record_type === "_workspace") {
    return (
      <p className="flex items-center gap-2 text-[13px] text-ink-2">
        <Undo2 size={14} aria-hidden /> Undo restored the previous version
      </p>
    );
  }
  const name = title(c.after, c.before) ?? c.record_id;
  const type = c.record_type.replace(/_/g, " ");
  const changed =
    c.op === "update" && c.before && c.after
      ? Object.keys({ ...c.before, ...c.after }).filter(
          (k) =>
            !k.startsWith("_") &&
            JSON.stringify(c.before?.[k]) !== JSON.stringify(c.after?.[k]),
        )
      : [];
  const sources = c.thread_ids.filter((t) => THREAD_ID.test(t)).slice(0, 2);

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[15px] leading-[1.35] font-semibold break-words">
        {name}
      </p>
      {c.op === "update" && changed.length ? (
        <ul className="flex flex-col gap-1.5">
          {changed.slice(0, 4).map((k) => (
            <li
              key={k}
              className="flex flex-wrap items-center gap-1.5 text-[13px] text-ink-2"
            >
              <span className="mr-0.5">{k.replace(/_/g, " ")}</span>
              <Pill value={fmt(c.before?.[k])} />
              <ArrowRight size={14} aria-hidden className="text-ink-3" />
              <Pill value={fmt(c.after?.[k])} status />
            </li>
          ))}
          {changed.length > 4 && (
            <li className="text-[13px] text-ink-3">
              and {changed.length - 4} more fields
            </li>
          )}
        </ul>
      ) : (
        <p className="text-[13px] text-ink-2">
          {c.op === "create"
            ? `New ${type}`
            : c.op === "delete"
              ? `Removed this ${type}`
              : `Updated ${type}`}
        </p>
      )}
      {sources.map((t) => (
        <a
          key={t}
          href={`https://mail.google.com/mail/u/0/#all/${t}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex w-fit items-center gap-1.5 rounded text-[13px] text-ink-2 hover:text-violet-ink hover:underline"
        >
          <Mail size={14} aria-hidden /> Open the email
        </a>
      ))}
    </div>
  );
}

function when(iso: string): string {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return today
    ? `Today, ${time}`
    : `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

export function ActivityFeed({
  changes,
  runs,
}: {
  changes: ChangeRead[];
  runs: RunRead[];
}) {
  if (!changes.length)
    return (
      <p className="py-6 text-sm text-ink-2">
        Nothing has changed yet. New and updated records from your inbox will
        show up here.
      </p>
    );
  const runById = new Map(runs.map((r) => [r.id, r]));
  const groups: { key: string; items: ChangeRead[] }[] = [];
  for (const c of changes) {
    const key = c.run_id ?? `undo-${c.id}`;
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(c);
    else groups.push({ key, items: [c] });
  }
  return (
    <ol className="divide-y divide-[rgb(12_26_46/0.08)]">
      {groups.map((g, gi) => {
        const run = runById.get(g.key);
        return (
          <li key={g.key} className="flex flex-col gap-3.5 py-3.5">
            <p className="flex items-center gap-2 text-xs text-ink-2">
              {gi === 0 && (
                <span aria-hidden className="size-1.5 rounded-full bg-violet" />
              )}
              {when(g.items[0].created_at)}
              {run ? ` · ${RUN_KIND[run.kind] ?? run.kind}` : ""}
              {g.items.length > 1 ? ` · ${g.items.length} changes` : ""}
            </p>
            {g.items.slice(0, 25).map((c) => (
              <ChangeItem key={c.id} c={c} />
            ))}
            {g.items.length > 25 && (
              <p className="text-[13px] text-ink-3">
                and {g.items.length - 25} more changes
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
