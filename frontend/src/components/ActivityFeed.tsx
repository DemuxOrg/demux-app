/**
 * Activity tab: record changes grouped by run, newest first. Each change shows
 * created / field before → after / deleted, with "open email" links.
 */
import type { ChangeRead, RunRead } from "@/lib/api";

const THREAD_ID = /^[0-9a-f]{8,32}$/;

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

function title(after: ChangeRead["after"], before: ChangeRead["before"]) {
  const rec = (after ?? before ?? {}) as Record<string, unknown>;
  const key = Object.keys(rec).find((k) =>
    /name|title|subject|label|description/.test(k),
  );
  return key ? fmt(rec[key]) : null;
}

function ChangeItem({ c }: { c: ChangeRead }) {
  if (c.record_type === "_workspace") {
    return <p className="text-sm text-gray-700">↶ Undo restored the previous version</p>;
  }
  const name = title(c.after, c.before) ?? c.record_id;
  const type = c.record_type.replace(/_/g, " ");
  let body: React.ReactNode = null;
  if (c.op === "update" && c.before && c.after) {
    const keys = Object.keys({ ...c.before, ...c.after }).filter(
      (k) => JSON.stringify(c.before?.[k]) !== JSON.stringify(c.after?.[k]),
    );
    body = (
      <ul className="mt-1 space-y-0.5">
        {keys.slice(0, 6).map((k) => (
          <li key={k} className="text-xs text-gray-600">
            <span className="text-gray-500">{k.replace(/_/g, " ")}</span>{" "}
            <span className="line-through">{fmt(c.before?.[k])}</span> →{" "}
            <span className="font-medium text-gray-900">{fmt(c.after?.[k])}</span>
          </li>
        ))}
      </ul>
    );
  }
  const verb = c.op === "create" ? "New" : c.op === "delete" ? "Deleted" : "Updated";
  return (
    <div>
      <p className="text-sm">
        <span className="text-gray-500">{verb} {type}</span>{" "}
        <span className="font-medium">{name}</span>
      </p>
      {body}
      {c.thread_ids.filter((t) => THREAD_ID.test(t)).slice(0, 2).map((t) => (
        <a
          key={t}
          href={`https://mail.google.com/mail/u/0/#all/${t}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mr-3 text-xs text-blue-600 hover:underline"
        >
          ↗ open email
        </a>
      ))}
    </div>
  );
}

export function ActivityFeed({
  changes,
  runs,
}: {
  changes: ChangeRead[];
  runs: RunRead[];
}) {
  if (!changes.length)
    return <p className="p-4 text-sm text-gray-500">No changes yet.</p>;
  const runById = new Map(runs.map((r) => [r.id, r]));
  const groups: { key: string; items: ChangeRead[] }[] = [];
  for (const c of changes) {
    const key = c.run_id ?? `undo-${c.id}`;
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(c);
    else groups.push({ key, items: [c] });
  }
  return (
    <div className="divide-y divide-gray-100">
      {groups.map((g) => {
        const run = runById.get(g.key);
        const when = new Date(g.items[0].created_at);
        return (
          <section key={g.key} className="space-y-2 p-4">
            <p className="text-xs text-gray-500">
              {when.toLocaleDateString()} {when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              {run ? ` · ${run.kind}` : ""}
              {g.items.length > 1 ? ` · ${g.items.length} changes` : ""}
            </p>
            {g.items.slice(0, 25).map((c) => (
              <ChangeItem key={c.id} c={c} />
            ))}
            {g.items.length > 25 && (
              <p className="text-xs text-gray-500">…and {g.items.length - 25} more</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
