/**
 * Layout blocks: DataTable, Board, Gallery, ListDetail, Timeline, Calendar, ViewTabs.
 * Each takes `records` (from records(data, type), usually filtered) plus field names.
 * Clicking a record opens it in the record sheet; every record can open its email.
 */
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";
import {
  autoFormat,
  daysUntil,
  fieldsOf,
  fmt,
  get,
  groupBy,
  isEmpty,
  label as toLabel,
  sortBy,
  specOf,
  toDate,
  tone,
  type Accessor,
  type FieldSpec,
  type Rec,
} from "../lib/data";
import { Button, Card, Dot, EmptyState, Note, OpenEmail, StatusBadge, Tabs, type TabItem } from "../ui/primitives";
import { FieldList, guessCard, RecordCard, titleOf, useFilters, useOpenRecord, Value, type CardSpec, type FilterOptions } from "./common";

const PAGE = 100;

function useCard(records: Rec[], card?: CardSpec): CardSpec {
  return React.useMemo(() => ({ ...guessCard(records ?? []), ...(card ?? {}) }), [records, card]);
}

/* ------------------------------------------------------------------ DataTable */

type Column = FieldSpec & {};
type ColumnObj = { field: Accessor; label?: string; format?: string; currency?: string; align?: "left" | "right" };

/**
 * A sortable table. columns: field names or { field, label, format, currency, align }.
 * search / facets add a toolbar (see useFilters). Rows open the record sheet.
 */
export function DataTable({
  records,
  columns,
  search,
  facets,
  defaultSort,
  emptyText,
  title,
}: {
  records: Rec[];
  columns?: Column[];
  search?: FilterOptions["search"];
  facets?: string[];
  defaultSort?: { field: string; dir?: "asc" | "desc" };
  emptyText?: string;
  title?: Accessor;
}) {
  const list = records ?? [];
  const { filtered, bar } = useFilters(list, { search: search ?? false, facets });
  const cols = React.useMemo(
    () => (columns?.length ? columns : fieldsOf(list).slice(0, 7)).map((c) => ({ ...specOf(c), align: (c as ColumnObj).align })),
    [columns, list],
  );
  const [sort, setSort] = React.useState<{ field: Accessor; dir: "asc" | "desc" } | null>(
    defaultSort ? { field: defaultSort.field, dir: defaultSort.dir ?? "asc" } : null,
  );
  const [limit, setLimit] = React.useState(PAGE);
  const open = useOpenRecord();
  const rows = sort ? sortBy(filtered, sort.field, sort.dir) : filtered;
  const showToolbar = !!search || !!facets?.length;

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {showToolbar && bar}
      {rows.length === 0 ? (
        <EmptyState title={list.length ? "No matches" : "No records yet"} description={list.length ? "Try another search or filter." : emptyText} />
      ) : (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full border-collapse text-sm tabular-nums">
            <thead>
              <tr>
                {cols.map((c, i) => {
                  const active = sort && sort.field === c.field;
                  const sample = typeof c.field === "string" ? (rows.find((r) => !isEmpty(r[c.field as string])) ?? rows[0]) : rows[0];
                  const right =
                    c.align === "right" ||
                    (c.align !== "left" &&
                      typeof c.field === "string" &&
                      ["money", "number", "percent"].includes(c.format === "auto" ? autoFormat(c.field, sample?.[c.field], sample) : c.format));
                  return (
                    <th
                      key={i}
                      aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                      className={cn(
                        "border-b border-line px-3 py-2.5 text-[13px] font-medium whitespace-nowrap text-ink-3",
                        right ? "text-right" : "text-left",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setSort(active ? (sort!.dir === "asc" ? { field: c.field, dir: "desc" } : null) : { field: c.field, dir: "asc" })
                        }
                        className="inline-flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 font-medium text-inherit hover:text-ink"
                      >
                        {c.label}
                        {active && (sort!.dir === "asc" ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />)}
                      </button>
                    </th>
                  );
                })}
                <th className="border-b border-line px-3 py-2.5" aria-label="Source" />
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((r) => (
                <tr
                  key={r.id}
                  onClick={() => open(r, { title })}
                  className="cursor-pointer transition-colors duration-150 hover:bg-surface-2"
                >
                  {cols.map((c, i) => {
                    const name = typeof c.field === "string" ? c.field : "";
                    const sample = name ? (rows.find((x) => !isEmpty(x[name])) ?? r) : r;
                    const f = c.format === "auto" && name ? autoFormat(name, sample[name], sample) : c.format;
                    const right = c.align === "right" || (c.align !== "left" && ["money", "number", "percent"].includes(f));
                    return (
                      <td
                        key={i}
                        className={cn(
                          "max-w-[320px] border-b border-line-soft px-3 py-2.5 align-top text-ink",
                          right && "text-right",
                          i === 0 && "font-medium",
                        )}
                      >
                        <Value record={r} spec={c} />
                      </td>
                    );
                  })}
                  <td className="border-b border-line-soft px-3 py-2.5 text-right whitespace-nowrap">
                    <OpenEmail record={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > limit && (
            <div className="flex justify-center pt-3">
              <Button size="sm" onClick={() => setLimit((l) => l + PAGE)}>
                Show more ({rows.length - limit})
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Board */

type ColumnDef = string | { value: string; label?: string };

/**
 * Kanban / Jira-style board: one column per value of `groupBy` (in `columns` order,
 * then any other values), a card per record (see CardSpec). Read-only.
 */
export function Board({
  records,
  groupBy: by,
  columns,
  card,
  hideEmpty = false,
}: {
  records: Rec[];
  groupBy: string;
  columns?: ColumnDef[];
  card?: CardSpec;
  hideEmpty?: boolean;
}) {
  const list = records ?? [];
  const guessed = useCard(list, card);
  const spec = { ...guessed, badge: guessed.badge === by ? undefined : guessed.badge };
  const open = useOpenRecord();
  const groups = groupBy(list, by);
  const norm = (v: string) => v.toLowerCase().replace(/[\s_-]+/g, " ").trim();
  const defs = (columns ?? []).map((c) => (typeof c === "string" ? { value: c, label: toLabel(c) } : { value: c.value, label: c.label ?? toLabel(c.value) }));
  const order: { value: string; label: string; items: Rec[] }[] = defs.map((d) => ({
    ...d,
    items: Object.entries(groups)
      .filter(([k]) => norm(k) === norm(d.value))
      .flatMap(([, v]) => v),
  }));
  for (const [k, items] of Object.entries(groups)) {
    if (!defs.some((d) => norm(d.value) === norm(k))) order.push({ value: k, label: k === "—" ? "No " + toLabel(by).toLowerCase() : toLabel(k), items });
  }
  const shown = hideEmpty ? order.filter((c) => c.items.length) : order;
  const statusLike = /(status|stage|state|phase)$/i.test(by) || shown.some((c) => tone(c.value) !== "neutral");
  if (!list.length) return <EmptyState title="No records yet" />;

  return (
    <div className="flex items-start gap-3 overflow-x-auto pb-1">
      {shown.map((col, i) => (
        <section key={col.value} aria-label={col.label} className="flex w-[272px] shrink-0 flex-col gap-2 rounded-col bg-surface-2 p-3">
          <h3 className="m-0 mx-0.5 mb-0.5 flex items-center gap-2 text-[13px] font-medium text-ink-2">
            {statusLike ? (
              <span aria-hidden className="inline-block size-[7px] shrink-0 rounded-full" style={{ background: `var(--dmx-${tone(col.value)})` }} />
            ) : (
              <Dot series={i + 2} />
            )}
            <span className="truncate">{col.label}</span>
            <span className="ml-auto text-ink-3 tabular-nums">{col.items.length}</span>
          </h3>
          {col.items.length ? (
            col.items.map((r) => <RecordCard key={r.id} record={r} card={spec} onOpen={() => open(r, { title: spec.title })} />)
          ) : (
            <Note className="px-1 py-3 text-center">Nothing here</Note>
          )}
        </section>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Gallery */

/** A responsive grid of record cards. */
export function Gallery({ records, card, min = 260 }: { records: Rec[]; card?: CardSpec; min?: number }) {
  const list = records ?? [];
  const spec = useCard(list, card);
  const open = useOpenRecord();
  if (!list.length) return <EmptyState title="No records yet" />;
  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${min}px, 100%), 1fr))` }}>
      {list.map((r) => (
        <RecordCard key={r.id} record={r} card={spec} onOpen={() => open(r, { title: spec.title })} />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ ListDetail */

/** A list on the left, the selected record's fields on the right (stacks on narrow screens). */
export function ListDetail({ records, item, fields }: { records: Rec[]; item?: CardSpec; fields?: FieldSpec[] }) {
  const list = records ?? [];
  const spec = useCard(list, item);
  const [selected, setSelected] = React.useState<string | null>(null);
  const current = list.find((r) => r.id === selected) ?? list[0];
  if (!list.length) return <EmptyState title="No records yet" />;
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(240px,340px)_1fr]">
      <ul role="listbox" aria-label="Records" className="m-0 flex max-h-[70vh] list-none flex-col gap-1 overflow-y-auto p-0">
        {list.map((r) => {
          const active = r.id === current?.id;
          return (
            <li key={r.id} role="option" aria-selected={active}>
              <button
                type="button"
                onClick={() => setSelected(r.id)}
                className={cn(
                  "flex w-full cursor-pointer items-start justify-between gap-2 rounded-card border px-3 py-2.5 text-left transition-colors duration-150",
                  active ? "border-accent-line bg-accent-tint" : "border-transparent bg-transparent hover:bg-surface-2",
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">{titleOf(r, spec.title)}</span>
                  {spec.subtitle && <span className="block truncate text-[13px] text-ink-3">{fmt.text(get(r, spec.subtitle))}</span>}
                </span>
                {spec.badge && !isEmpty(get(r, spec.badge)) && <StatusBadge value={get(r, spec.badge)} className="shrink-0" />}
              </button>
            </li>
          );
        })}
      </ul>
      {current && (
        <Card className="self-start px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="text-lg font-semibold tracking-[-0.015em] text-ink">{titleOf(current, spec.title)}</div>
            <OpenEmail record={current} variant="secondary" />
          </div>
          <FieldList record={current} fields={fields} />
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Timeline */

function dayLabel(d: Date): string {
  const n = daysUntil(d);
  if (n === 0) return "Today";
  if (n === 1) return "Tomorrow";
  if (n === -1) return "Yesterday";
  return new Intl.DateTimeFormat("en", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...(d.getFullYear() === new Date().getFullYear() ? {} : { year: "numeric" }),
  }).format(d);
}

/**
 * Records along a date field, grouped by day (or month). With split (default), upcoming
 * dates come first, soonest first, then past ones, newest first.
 */
export function Timeline({
  records,
  date,
  title,
  subtitle,
  badge,
  meta,
  groupBy: unit = "day",
  split = true,
}: {
  records: Rec[];
  date: Accessor;
  title?: Accessor;
  subtitle?: Accessor;
  badge?: Accessor;
  meta?: FieldSpec[];
  groupBy?: "day" | "month";
  split?: boolean;
}) {
  const list = records ?? [];
  const spec = useCard(list, { title, subtitle, badge, meta });
  const open = useOpenRecord();
  if (!list.length) return <EmptyState title="No records yet" />;

  const dated = list.map((r) => ({ r, d: toDate(get(r, date)) }));
  const keyOf = (d: Date) =>
    unit === "month" ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}` : d.toDateString();
  const labelOf = (d: Date) =>
    unit === "month"
      ? new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(d)
      : dayLabel(d);

  const sections: { name?: string; items: { r: Rec; d: Date }[]; dir: 1 | -1 }[] = [];
  const withDate = dated.filter((x): x is { r: Rec; d: Date } => !!x.d);
  if (split) {
    const upcoming = withDate.filter((x) => (daysUntil(x.d) ?? 0) >= 0);
    const past = withDate.filter((x) => (daysUntil(x.d) ?? 0) < 0);
    if (upcoming.length) sections.push({ name: "Upcoming", items: upcoming, dir: 1 });
    if (past.length) sections.push({ name: "Past", items: past, dir: -1 });
  } else if (withDate.length) sections.push({ items: withDate, dir: -1 });
  const undated = dated.filter((x) => !x.d).map((x) => x.r);

  return (
    <div className="flex flex-col gap-6">
      {sections.map((sec) => {
        const sorted = [...sec.items].sort((a, b) => sec.dir * (a.d.getTime() - b.d.getTime()));
        const groups: { key: string; label: string; items: Rec[] }[] = [];
        for (const x of sorted) {
          const k = keyOf(x.d);
          const g = groups.find((y) => y.key === k);
          if (g) g.items.push(x.r);
          else groups.push({ key: k, label: labelOf(x.d), items: [x.r] });
        }
        return (
          <section key={sec.name ?? "all"} className="flex flex-col gap-3">
            {sec.name && <h3 className="m-0 text-[13px] font-medium text-ink-3">{sec.name}</h3>}
            <ol className="m-0 flex list-none flex-col gap-4 p-0">
              {groups.map((g) => (
                <li key={g.key} className="grid gap-2 sm:grid-cols-[132px_1fr]">
                  <div className="pt-3 text-[13px] font-medium text-ink-2">{g.label}</div>
                  <div className="flex flex-col gap-2 border-l-2 border-line-soft pl-4">
                    {g.items.map((r) => (
                      <RecordCard key={r.id} record={r} card={spec} onOpen={() => open(r, { title: spec.title })} />
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        );
      })}
      {undated.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="m-0 text-[13px] font-medium text-ink-3">No date</h3>
          {undated.map((r) => (
            <RecordCard key={r.id} record={r} card={spec} onOpen={() => open(r, { title: spec.title })} />
          ))}
        </section>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Calendar */

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** A month calendar of records on a date field; arrows move between months. */
export function Calendar({ records, date, title, badge }: { records: Rec[]; date: Accessor; title?: Accessor; badge?: Accessor }) {
  const list = records ?? [];
  const spec = useCard(list, { title, badge });
  const open = useOpenRecord();
  const dated = list.map((r) => ({ r, d: toDate(get(r, date)) })).filter((x): x is { r: Rec; d: Date } => !!x.d);
  const initial = React.useMemo(() => {
    const upcoming = dated.filter((x) => (daysUntil(x.d) ?? -1) >= 0).sort((a, b) => a.d.getTime() - b.d.getTime())[0];
    const d = upcoming?.d ?? new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }, []); // eslint-disable-line
  const [month, setMonth] = React.useState(initial);
  const y = month.getFullYear();
  const m = month.getMonth();
  const offset = (new Date(y, m, 1).getDay() + 6) % 7;
  const days = new Date(y, m + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array.from({ length: offset }, () => null),
    ...Array.from({ length: days }, (_, i) => new Date(y, m, i + 1)),
  ];
  while (cells.length % 7) cells.push(null);
  const byDay = groupBy(
    dated.map((x) => ({ ...x.r, __day: x.d.toDateString() }) as Rec),
    "__day",
  );
  const monthName = new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(month);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Button size="icon" variant="ghost" aria-label="Previous month" onClick={() => setMonth(new Date(y, m - 1, 1))}>
          <ChevronLeft />
        </Button>
        <div className="min-w-[140px] text-center text-[15px] font-semibold text-ink">{monthName}</div>
        <Button size="icon" variant="ghost" aria-label="Next month" onClick={() => setMonth(new Date(y, m + 1, 1))}>
          <ChevronRight />
        </Button>
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[640px] grid-cols-7 overflow-hidden rounded-card border border-line">
          {WEEKDAYS.map((w) => (
            <div key={w} className="border-b border-line bg-surface-2 px-2 py-1.5 text-xs font-medium text-ink-3">
              {w}
            </div>
          ))}
          {cells.map((d, i) => {
            const items = d ? (byDay[d.toDateString()] ?? []) : [];
            const today = d && daysUntil(d) === 0;
            return (
              <div key={i} className={cn("min-h-[96px] border-b border-l border-line-soft p-1.5 [&:nth-child(7n+1)]:border-l-0", !d && "bg-surface-2/60")}>
                {d && (
                  <div className={cn("mb-1 inline-grid size-6 place-items-center rounded-full text-xs tabular-nums", today ? "bg-accent font-semibold text-white" : "text-ink-3")}>
                    {d.getDate()}
                  </div>
                )}
                <div className="flex flex-col gap-1">
                  {items.slice(0, 3).map((r) => {
                    const t = spec.badge ? tone(get(r, spec.badge)) : "neutral";
                    return (
                      <button
                        key={r.id}
                        type="button"
                        onClick={() => open(r, { title: spec.title })}
                        className={cn(
                          "w-full cursor-pointer truncate rounded-[6px] border-0 px-1.5 py-0.5 text-left text-xs font-medium",
                          { success: "bg-success-bg text-success", danger: "bg-danger-bg text-danger", warning: "bg-warning-bg text-warning", info: "bg-info-bg text-info", neutral: "bg-accent-soft text-accent-ink" }[t],
                        )}
                      >
                        {titleOf(r, spec.title)}
                      </button>
                    );
                  })}
                  {items.length > 3 && <span className="px-1.5 text-xs text-ink-3">+{items.length - 3} more</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {dated.length < list.length && <Note>{list.length - dated.length} without a date are not shown.</Note>}
    </div>
  );
}

/* ------------------------------------------------------------------ ViewTabs */

export type View = { id: string; label: React.ReactNode; content?: React.ReactNode; render?: () => React.ReactNode };

/** Switch between layouts of the same records. `toolbar` sits on the right (e.g. useFilters' bar). */
export function ViewTabs({ views, defaultView, toolbar }: { views: View[]; defaultView?: string; toolbar?: React.ReactNode }) {
  const tabs: TabItem[] = (views ?? []).map((v) => ({ id: v.id, label: v.label, content: v.content ?? v.render?.() }));
  if (tabs.length === 1)
    return (
      <div className="flex flex-col gap-4">
        {toolbar && <div className="flex flex-wrap justify-end gap-2">{toolbar}</div>}
        {tabs[0].content}
      </div>
    );
  return <Tabs tabs={tabs} defaultValue={defaultView} toolbar={toolbar} />;
}
