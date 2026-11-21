/**
 * Shared block pieces: formatted values, record cards, the record sheet every block opens
 * on click, and useFilters (search + facet selects).
 */
import * as React from "react";
import { cn } from "../lib/cn";
import {
  autoFormat,
  currencyFor,
  fieldsOf,
  fmt,
  get,
  isEmpty,
  label as toLabel,
  specOf,
  type Accessor,
  type FieldSpec,
  type Rec,
} from "../lib/data";
import { Card, OpenEmail, Row, SearchInput, Select, Sheet, StatusBadge, Tag } from "../ui/primitives";

/* ------------------------------------------------------------------ values */

/** One field of a record, formatted (status → pill, money, dates, lists → tags). */
export function Value({ record, spec, className }: { record: Rec; spec: FieldSpec; className?: string }) {
  const s = specOf(spec);
  const v = get(record, s.field);
  const name = typeof s.field === "string" ? s.field : "";
  const f = s.format === "auto" ? autoFormat(name, v, record) : s.format;
  if (isEmpty(v)) return <span className={cn("text-ink-3", className)}>—</span>;
  if (f === "status") return <StatusBadge value={v} className={className} />;
  if (f === "tag") return <Tag className={className}>{fmt.text(v)}</Tag>;
  if (f === "list" && Array.isArray(v))
    return (
      <span className={cn("inline-flex flex-wrap gap-1", className)}>
        {v.map((x, i) => (
          <Tag key={i}>{fmt.text(x)}</Tag>
        ))}
      </span>
    );
  const text = fmt.as(f, v, record, name, s.currency);
  const numeric = f === "money" || f === "number" || f === "percent";
  return <span className={cn(numeric && "tabular-nums", className)}>{text}</span>;
}

/* ------------------------------------------------------------------ guessing */

const TITLE_NAMES = /^(title|name|subject|item|product|description|company|vendor|merchant|supplier|client|customer|role|position|event|property|service)$/i;

/** A sensible title / subtitle / badge / meta when the app gives none. */
export function guessCard(list: Rec[]): Required<Pick<CardSpec, "title">> & CardSpec {
  const fields = fieldsOf(list);
  const sample = list.find(Boolean) ?? ({} as Rec);
  const kind = (f: string) => autoFormat(f, sample[f], sample);
  const title = fields.find((f) => TITLE_NAMES.test(f)) ?? fields.find((f) => kind(f) === "text") ?? "id";
  const badge = fields.find((f) => kind(f) === "status");
  const rest = fields.filter((f) => f !== title && f !== badge);
  const subtitle = rest.find((f) => kind(f) === "text");
  const meta = rest.filter((f) => f !== subtitle).slice(0, 3);
  return { title, subtitle, badge, meta };
}

export function titleOf(r: Rec, a?: Accessor): string {
  const v = a ? get(r, a) : undefined;
  return isEmpty(v) ? r.id : fmt.text(v);
}

/* ------------------------------------------------------------------ sheet */

type SheetState = { record: Rec; title?: Accessor; fields?: FieldSpec[] } | null;
const SheetContext = React.createContext<(s: SheetState) => void>(() => {});

/** Provides the one record sheet blocks open on click. Wraps the App (runtime). */
export function RecordSheetProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<SheetState>(null);
  return (
    <SheetContext.Provider value={setState}>
      {children}
      <RecordSheet
        record={state?.record ?? null}
        title={state?.title}
        fields={state?.fields}
        open={!!state}
        onOpenChange={(o) => !o && setState(null)}
      />
    </SheetContext.Provider>
  );
}

/** Open a record in the side sheet: useOpenRecord()(record, { title, fields }). */
export function useOpenRecord() {
  const set = React.useContext(SheetContext);
  return React.useCallback(
    (record: Rec, opts: { title?: Accessor; fields?: FieldSpec[] } = {}) => set({ record, ...opts }),
    [set],
  );
}

/** Every field of a record as label / value rows. */
export function FieldList({ record, fields }: { record: Rec; fields?: FieldSpec[] }) {
  const specs = fields ?? fieldsOf([record]);
  return (
    <dl className="m-0 flex flex-col">
      {specs.map((spec, i) => {
        const s = specOf(spec);
        return (
          <div key={i} className="grid grid-cols-[minmax(96px,36%)_1fr] gap-3 border-b border-line-soft py-2.5 last:border-b-0">
            <dt className="text-[13px] text-ink-3">{s.label || "—"}</dt>
            <dd className="m-0 min-w-0 text-sm break-words text-ink">
              <Value record={record} spec={spec} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function RecordSheet({
  record,
  open,
  onOpenChange,
  title,
  fields,
}: {
  record: Rec | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: Accessor;
  fields?: FieldSpec[];
}) {
  const t = record ? titleOf(record, title ?? guessCard([record]).title) : "";
  return (
    <Sheet
      open={open && !!record}
      onOpenChange={onOpenChange}
      title={t}
      actions={record ? <OpenEmail record={record} variant="secondary" /> : null}
    >
      {record && <FieldList record={record} fields={fields} />}
    </Sheet>
  );
}

/* ------------------------------------------------------------------ cards */

export type CardSpec = {
  title?: Accessor;
  subtitle?: Accessor;
  badge?: Accessor;
  meta?: FieldSpec[];
  tags?: Accessor;
  amount?: FieldSpec;
  highlight?: (r: Rec) => boolean;
};

/** A record as a card (board, gallery): title + status, subtitle, meta, "Open email". */
export function RecordCard({ record, card, onOpen }: { record: Rec; card: CardSpec; onOpen?: () => void }) {
  const tags = card.tags ? get(record, card.tags) : undefined;
  const amount = card.amount ? specOf(card.amount) : null;
  const hasAmount = !!amount && !isEmpty(get(record, amount.field));
  return (
    <Card onClick={onOpen} highlighted={card.highlight?.(record)}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[15px] leading-snug font-semibold break-words text-ink">{titleOf(record, card.title)}</div>
          {card.subtitle && !isEmpty(get(record, card.subtitle)) && (
            <div className="mt-0.5 truncate text-[13px] text-ink-3">{fmt.text(get(record, card.subtitle))}</div>
          )}
        </div>
        {hasAmount ? (
          <span className="shrink-0 text-[15px] font-semibold text-ink">
            <Value record={record} spec={card.amount!} />
          </span>
        ) : card.badge && !isEmpty(get(record, card.badge)) ? (
          <StatusBadge value={get(record, card.badge)} className="shrink-0" />
        ) : null}
      </div>
      {hasAmount && card.badge && !isEmpty(get(record, card.badge)) && (
        <div>
          <StatusBadge value={get(record, card.badge)} />
        </div>
      )}
      {Array.isArray(tags) && tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map((t, i) => (
            <Tag key={i}>{fmt.text(t)}</Tag>
          ))}
        </div>
      )}
      <div className="-mb-1 flex items-end justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5 text-[13px]">
          {(card.meta ?? []).map((m, i) => {
            const s = specOf(m);
            return (
              <span key={i} className="min-w-0 text-ink-3">
                {s.label}: <Value record={record} spec={m} className="text-ink-2" />
              </span>
            );
          })}
        </div>
        <span className="-mr-1.5 shrink-0">
          <OpenEmail record={record} variant="icon" />
        </span>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ filters */

export type FilterOptions = {
  /** Fields the search box looks in (true = every field). */
  search?: Accessor[] | boolean;
  /** Fields with a select each ("All" + their values). */
  facets?: string[];
  placeholder?: string;
};

function haystack(r: Rec, fields: Accessor[] | true): string {
  const keys: Accessor[] = fields === true ? Object.keys(r).filter((k) => !k.startsWith("_")) : fields;
  return keys
    .map((k) => fmt.text(get(r, k)))
    .join(" ")
    .toLowerCase();
}

/**
 * Search box + facet selects over a list. Call it in App:
 *   const { filtered, bar } = useFilters(list, { search: ["name"], facets: ["status"] })
 * then render {bar} (e.g. as ViewTabs' toolbar) and pass `filtered` to blocks.
 */
export function useFilters(list: Rec[], opts: FilterOptions = {}) {
  const [query, setQuery] = React.useState("");
  const [facetValues, setFacetValues] = React.useState<Record<string, string>>({});
  const items = list ?? [];
  const searchFields = opts.search === undefined ? true : opts.search;
  const facets = opts.facets ?? [];

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((r) => {
      for (const f of facets) {
        const want = facetValues[f];
        if (!want) continue;
        const v = r[f];
        const vals = Array.isArray(v) ? v.map(String) : [String(v ?? "")];
        if (!vals.includes(want)) return false;
      }
      if (q && searchFields !== false && !haystack(r, searchFields).includes(q)) return false;
      return true;
    });
  }, [items, query, facetValues, facets.join("|"), searchFields]); // eslint-disable-line

  const bar = (
    <Row gap="sm">
      {searchFields !== false && <SearchInput value={query} onChange={setQuery} placeholder={opts.placeholder ?? "Search…"} />}
      {facets.map((f) => {
        const values = Array.from(
          new Set(items.flatMap((r) => (Array.isArray(r[f]) ? (r[f] as unknown[]) : [r[f]])).filter((v) => !isEmpty(v)).map(String)),
        ).sort((a, b) => a.localeCompare(b));
        return (
          <Select
            key={f}
            value={facetValues[f] ?? ""}
            onChange={(v) => setFacetValues((s) => ({ ...s, [f]: v }))}
            options={values}
            label={toLabel(f)}
            placeholder="All"
          />
        );
      })}
    </Row>
  );
  return { filtered, bar, query, setQuery, facetValues, setFacetValues };
}

export function currencyLabel(r: Rec, field: Accessor): string | undefined {
  return currencyFor(r, field);
}
