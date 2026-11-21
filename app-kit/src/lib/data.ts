/**
 * Data helpers for generated apps: read records, format values, group and total them.
 * Everything tolerates null, missing and unexpected values (records come from email).
 */

export type Rec = Record<string, unknown> & {
  id: string;
  _sources?: { message_id: string; thread_id: string }[];
  _updated_at?: string;
};
export type Data = Record<string, Record<string, Record<string, unknown>> | undefined>;

export type Format =
  | "auto"
  | "text"
  | "money"
  | "number"
  | "percent"
  | "date"
  | "datetime"
  | "relative"
  | "status"
  | "tag"
  | "bool"
  | "list";

export type Accessor = string | ((r: Rec) => unknown);
export type FieldSpec =
  | Accessor
  | {
      field: Accessor;
      label?: string;
      format?: Format;
      /** Currency code ("EUR") or the name of the field holding it. */
      currency?: string;
    };

export type Tone = "success" | "danger" | "warning" | "info" | "neutral";

/** The non-system record type names in the data, in order. */
export function types(data: Data | null | undefined): string[] {
  return Object.keys(data ?? {}).filter((t) => !t.startsWith("_"));
}

/** Records of one type as an array, each with its `id`. Missing type → []. */
export function records(data: Data | null | undefined, type: string): Rec[] {
  const recs = data?.[type];
  if (!recs || typeof recs !== "object") return [];
  return Object.entries(recs).map(([id, r]) => ({ ...(r ?? {}), id }) as Rec);
}

export function get(r: Rec, a: Accessor): unknown {
  return typeof a === "function" ? a(r) : r?.[a];
}

export function specOf(spec: FieldSpec): {
  field: Accessor;
  label: string;
  format: Format;
  currency?: string;
} {
  if (typeof spec === "object" && spec !== null && "field" in spec) {
    return {
      field: spec.field,
      label: spec.label ?? (typeof spec.field === "string" ? label(spec.field) : ""),
      format: spec.format ?? "auto",
      currency: spec.currency,
    };
  }
  return {
    field: spec as Accessor,
    label: typeof spec === "string" ? label(spec) : "",
    format: "auto",
  };
}

/** "due_date" → "Due date". */
export function label(name: string): string {
  const t = String(name ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .trim()
    .toLowerCase();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
}

const ISO = /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const MONEY_NAME = /(amount|total|price|cost|balance|fee|salary|rent|paid|due|value|budget|spend|refund)/i;
const STATUS_NAME = /(status|stage|state|phase)$/i;

export function isEmpty(v: unknown): boolean {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
}

/** A Date from an ISO date or date-time string (dates are local, not UTC). */
export function toDate(v: unknown): Date | null {
  if (v instanceof Date) return Number.isNaN(v.getTime()) ? null : v;
  if (typeof v !== "string" || !v) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Whole days from today to the date (negative when past); null when not a date. */
export function daysUntil(v: unknown): number | null {
  const d = toDate(v);
  if (!d) return null;
  return Math.round((startOfDay(d) - startOfDay(new Date())) / 86_400_000);
}

export function isPast(v: unknown): boolean {
  const n = daysUntil(v);
  return n !== null && n < 0;
}

/** The currency for a money field: an explicit code, `<field>_currency`, or `currency`. */
export function currencyFor(r: Rec, field: Accessor, given?: string): string | undefined {
  if (given) {
    const fromField = r?.[given];
    if (typeof fromField === "string" && fromField) return fromField;
    if (/^[A-Z]{3}$/.test(given)) return given;
  }
  if (typeof field === "string") {
    const base = field.replace(/_?(amount|total|price|cost|value)$/i, "");
    for (const k of [`${field}_currency`, `${base}_currency`, "currency"]) {
      const c = r?.[k];
      if (typeof c === "string" && c) return c;
    }
  }
  const c = r?.currency;
  return typeof c === "string" && c ? c : undefined;
}

/** The format a value gets when none was given. */
export function autoFormat(name: string, v: unknown, r?: Rec): Format {
  if (typeof v === "boolean") return "bool";
  if (Array.isArray(v)) return "list";
  if (STATUS_NAME.test(name) && typeof v === "string") return "status";
  if (typeof v === "number") {
    if (MONEY_NAME.test(name) && r && currencyFor(r, name)) return "money";
    return "number";
  }
  if (typeof v === "string" && ISO.test(v)) return v.length > 10 ? "datetime" : "date";
  return "text";
}

const sameYear = (d: Date) => d.getFullYear() === new Date().getFullYear();

export const fmt = {
  text(v: unknown): string {
    if (isEmpty(v)) return "—";
    if (Array.isArray(v)) return v.map((x) => fmt.text(x)).join(", ");
    if (typeof v === "boolean") return v ? "Yes" : "No";
    if (typeof v === "number") return fmt.number(v);
    return String(v);
  },
  number(v: unknown, digits?: number): string {
    const n = typeof v === "number" ? v : Number(v);
    if (isEmpty(v) || Number.isNaN(n)) return "—";
    return new Intl.NumberFormat("en", { maximumFractionDigits: digits ?? 2 }).format(n);
  },
  percent(v: unknown): string {
    const n = typeof v === "number" ? v : Number(v);
    if (isEmpty(v) || Number.isNaN(n)) return "—";
    return `${fmt.number(n <= 1 && n >= -1 ? n * 100 : n, 1)}%`;
  },
  money(amount: unknown, currency?: string): string {
    const n = typeof amount === "number" ? amount : Number(amount);
    if (isEmpty(amount) || Number.isNaN(n)) return "—";
    if (currency && /^[A-Za-z]{3}$/.test(currency)) {
      try {
        return new Intl.NumberFormat("en", {
          style: "currency",
          currency: currency.toUpperCase(),
          maximumFractionDigits: Number.isInteger(n) ? 0 : 2,
        }).format(n);
      } catch {
        /* unknown code: fall through */
      }
    }
    return currency ? `${fmt.number(n)} ${currency}` : fmt.number(n);
  },
  date(v: unknown): string {
    const d = toDate(v);
    if (!d) return isEmpty(v) ? "—" : String(v);
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      ...(sameYear(d) ? {} : { year: "numeric" }),
    }).format(d);
  },
  datetime(v: unknown): string {
    const d = toDate(v);
    if (!d) return isEmpty(v) ? "—" : String(v);
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      ...(sameYear(d) ? {} : { year: "numeric" }),
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
  },
  /** "today", "tomorrow", "in 3 days", "2 weeks ago". */
  relative(v: unknown): string {
    const n = daysUntil(v);
    if (n === null) return isEmpty(v) ? "—" : String(v);
    if (n === 0) return "today";
    if (n === 1) return "tomorrow";
    if (n === -1) return "yesterday";
    const abs = Math.abs(n);
    const unit =
      abs >= 60 ? `${Math.round(abs / 30)} months` : abs >= 14 ? `${Math.round(abs / 7)} weeks` : `${abs} days`;
    return n > 0 ? `in ${unit}` : `${unit} ago`;
  },
  label,
  /** Format by name ("money", "date", …), as columns and cards do. */
  as(format: Format, v: unknown, r?: Rec, name = "", currency?: string): string {
    const f = format === "auto" ? autoFormat(name, v, r) : format;
    switch (f) {
      case "money":
        return fmt.money(v, r ? currencyFor(r, name, currency) : currency);
      case "number":
        return fmt.number(v);
      case "percent":
        return fmt.percent(v);
      case "date":
        return fmt.date(v);
      case "datetime":
        return fmt.datetime(v);
      case "relative":
        return fmt.relative(v);
      case "status":
        return isEmpty(v) ? "—" : label(String(v));
      default:
        return fmt.text(v);
    }
  },
};

const TONES: [Tone, RegExp][] = [
  ["danger", /\b(overdue|rejected|failed|cancell?ed|declined|lost|expired|returned to sender|refused|bounced|disputed|late payment)\b/],
  ["warning", /\b(delayed|waiting|pending|on[ _-]hold|late|due soon|action needed|needs? review|exception|partially|partial)\b/],
  ["success", /\b(paid|approved|delivered|done|complete|completed|accepted|confirmed|received|won|resolved|active|hired|offer)\b/],
  ["info", /\b(in[ _-]transit|shipped|sent|scheduled|in[ _-]progress|booked|out[ _-]for[ _-]delivery|processing|interview(ing)?|applied|submitted|open|new|ordered)\b/],
];

/** The status tone for a value ("Paid" → success, "Overdue" → danger, …). */
export function tone(v: unknown): Tone {
  const s = String(v ?? "")
    .toLowerCase()
    .replace(/_/g, " ");
  for (const [t, re] of TONES) if (re.test(s)) return t;
  return "neutral";
}

function cmp(a: unknown, b: unknown): number {
  if (isEmpty(a) && isEmpty(b)) return 0;
  if (isEmpty(a)) return 1;
  if (isEmpty(b)) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  const da = typeof a === "string" && ISO.test(a) ? toDate(a) : null;
  const db = typeof b === "string" && ISO.test(b) ? toDate(b) : null;
  if (da && db) return da.getTime() - db.getTime();
  return String(a).localeCompare(String(b), "en", { numeric: true, sensitivity: "base" });
}

/** A sorted copy; empty values always last. */
export function sortBy(list: Rec[], a: Accessor, dir: "asc" | "desc" = "asc"): Rec[] {
  const sign = dir === "desc" ? -1 : 1;
  return [...(list ?? [])].sort((x, y) => {
    const vx = get(x, a);
    const vy = get(y, a);
    if (isEmpty(vx) || isEmpty(vy)) return cmp(vx, vy);
    return sign * cmp(vx, vy);
  });
}

/** { value: records } in first-seen order; empty values under "—". */
export function groupBy(list: Rec[], a: Accessor): Record<string, Rec[]> {
  const out: Record<string, Rec[]> = {};
  for (const r of list ?? []) {
    const v = get(r, a);
    const keys = Array.isArray(v) ? (v.length ? v : [null]) : [v];
    for (const k of keys) {
      const key = isEmpty(k) ? "—" : String(k);
      (out[key] ??= []).push(r);
    }
  }
  return out;
}

export function uniq(list: Rec[], a: Accessor): string[] {
  return Object.keys(groupBy(list, a)).filter((k) => k !== "—");
}

export function sumBy(list: Rec[], a: Accessor): number {
  let total = 0;
  for (const r of list ?? []) {
    const n = Number(get(r, a));
    if (!Number.isNaN(n)) total += n;
  }
  return total;
}

export function countBy(list: Rec[], a: Accessor): { label: string; value: number }[] {
  return aggregate(list, { by: a });
}

export type Point = { label: string; value: number; key?: string };

/**
 * Group and total records for charts and stats: [{ label, value }].
 * op: "count" (default without `value`), "sum" (default with `value`), "avg", "max".
 */
export function aggregate(
  list: Rec[],
  opts: {
    by: Accessor;
    value?: Accessor;
    op?: "count" | "sum" | "avg" | "max";
    sort?: "value" | "label" | "none";
    limit?: number;
  },
): Point[] {
  const op = opts.op ?? (opts.value ? "sum" : "count");
  const groups = groupBy(list, opts.by);
  let points: Point[] = Object.entries(groups).map(([k, rs]) => {
    let value = rs.length;
    if (op !== "count" && opts.value) {
      const nums = rs.map((r) => Number(get(r, opts.value!))).filter((n) => !Number.isNaN(n));
      value =
        op === "sum"
          ? nums.reduce((s, n) => s + n, 0)
          : op === "avg"
            ? nums.length
              ? nums.reduce((s, n) => s + n, 0) / nums.length
              : 0
            : nums.length
              ? Math.max(...nums)
              : 0;
    }
    return { label: k === "—" ? "None" : label(k) || k, value, key: k };
  });
  if ((opts.sort ?? "value") === "value") points.sort((a, b) => b.value - a.value);
  if (opts.sort === "label") points.sort((a, b) => cmp(a.label, b.label));
  if (opts.limit && points.length > opts.limit) {
    const kept = points.slice(0, opts.limit - 1);
    const rest = points.slice(opts.limit - 1).reduce((s, p) => s + p.value, 0);
    points = [...kept, { label: "Other", value: rest, key: "__other" }];
  }
  return points;
}

/** Totals per month of a date field, oldest first, months without records filled in. */
export function byMonth(
  list: Rec[],
  date: Accessor,
  opts: { value?: Accessor; op?: "count" | "sum" } = {},
): Point[] {
  const op = opts.op ?? (opts.value ? "sum" : "count");
  const totals = new Map<string, number>();
  for (const r of list ?? []) {
    const d = toDate(get(r, date));
    if (!d) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const add = op === "sum" && opts.value ? Number(get(r, opts.value)) || 0 : 1;
    totals.set(key, (totals.get(key) ?? 0) + add);
  }
  if (!totals.size) return [];
  const keys = [...totals.keys()].sort();
  const [y0, m0] = keys[0].split("-").map(Number);
  const [y1, m1] = keys[keys.length - 1].split("-").map(Number);
  const spansYears = y0 !== y1;
  const out: Point[] = [];
  for (let y = y0, m = m0; y < y1 || (y === y1 && m <= m1); m === 12 ? ((m = 1), y++) : m++) {
    const key = `${y}-${String(m).padStart(2, "0")}`;
    const d = new Date(y, m - 1, 1);
    const name = new Intl.DateTimeFormat("en", { month: "short" }).format(d);
    out.push({ key, label: spansYears ? `${name} ${String(y).slice(2)}` : name, value: totals.get(key) ?? 0 });
  }
  return out;
}

/** The thread of the newest email a record came from (for demux.openSource). */
export function latestThread(r: Rec | null | undefined): string | null {
  const s = r?._sources;
  return Array.isArray(s) && s.length ? (s[s.length - 1]?.thread_id ?? null) : null;
}

export function openEmail(r: Rec | null | undefined): void {
  const t = latestThread(r);
  const bridge = (window as unknown as { demux?: { openSource(id: string): void } }).demux;
  if (t && bridge) bridge.openSource(t);
}

/** Updated by a sync in the last `hours` (default 6). */
export function isRecent(r: Rec | null | undefined, hours = 6): boolean {
  const d = toDate(r?._updated_at);
  return !!d && Date.now() - d.getTime() < hours * 3_600_000;
}

/** Public fields of a record, in a stable order (for sheets and auto columns). */
export function fieldsOf(list: Rec[]): string[] {
  const seen: string[] = [];
  for (const r of list ?? [])
    for (const k of Object.keys(r ?? {}))
      if (k !== "id" && !k.startsWith("_") && !seen.includes(k)) seen.push(k);
  // Currency fields are shown with their amount, not alone.
  return seen.filter((k) => !/(^|_)currency$/.test(k) || !seen.some((o) => o !== k && MONEY_NAME.test(o)));
}
