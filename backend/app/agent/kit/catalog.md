# Kit reference

Everything below is a global: no imports. Write JSX. `useState`, `useMemo`, `useEffect`, `useRef`, `useCallback` and `Fragment` are the React ones.

Field arguments (`title`, `groupBy`, `date`, columns, meta…) take a field name (`"due_date"`) or a function (`r => r.first + " " + r.last`). A column / meta entry can also be `{ field, label, format, currency }`. Formats: `"auto"` (default: status fields become pills, numbers with a currency field become money, ISO dates become dates), `"text"`, `"money"`, `"number"`, `"percent"`, `"date"`, `"datetime"`, `"relative"` ("in 3 days"), `"status"`, `"tag"`, `"bool"`, `"list"`. `currency` is a code (`"EUR"`) or the field holding it; by default `<field>_currency` or `currency` is used.

## Data
- `records(data, "type")` → array of records, each with `id`, its fields, `_sources`, `_updated_at`. Missing type → `[]`.
- `types(data)` → record type names.
- `fmt.money(n, "EUR")`, `fmt.date(v)`, `fmt.datetime(v)`, `fmt.relative(v)`, `fmt.number(n)`, `fmt.percent(n)`, `fmt.text(v)` ("—" when empty), `fmt.label("due_date")` → "Due date".
- `groupBy(list, field)` → `{ value: [records] }`. `uniq(list, field)` → values. `sortBy(list, field, "asc" | "desc")` (empty last).
- `sumBy(list, field)` → number. `countBy(list, field)` → `[{ label, value }]`.
- `aggregate(list, { by, value?, op?: "count" | "sum" | "avg" | "max", sort?: "value" | "label", limit? })` → `[{ label, value }]` (with `limit`, the rest becomes "Other").
- `byMonth(list, dateField, { value?, op? })` → `[{ label: "Mar", value }]`, oldest first, empty months filled.
- `daysUntil(date)` (negative when past, null when not a date), `isPast(date)`, `toDate(v)`, `isEmpty(v)`.
- `tone(value)` → `"success" | "danger" | "warning" | "info" | "neutral"` from status words.
- `latestThread(record)`, `openEmail(record)`: the record's newest source email.

## Layout
- `<Page title description actions>` the app's top. Put everything inside one Page.
- `<Section title description actions>` a titled group.
- `<Stack gap>` vertical, `<Row gap align justify>` horizontal and wrapping, `<Grid min={240}>` responsive columns. `gap`: number of px or `"sm" | "md" | "lg"`.
- `<Note>` small muted text. `<Separator />`.

## Blocks (one per layout the user picked)
Every block opens a clicked record in a side sheet with all its fields and an "Open email" button.

- `<DataTable records columns search facets defaultSort={{ field, dir }} />` sortable table. `columns` default: the first fields. `search`: `true` or field names; `facets`: field names with a select each.
- `<Board records groupBy="status" columns={["applied", "interview", "offer"]} card={{ title, subtitle, meta: [...], badge, amount, tags }} />` Kanban / Jira-style columns, one per value (listed `columns` first, in order, even when empty; other values after). Read-only.
- `<Gallery records card min={260} />` grid of record cards.
- `<ListDetail records item={{ title, subtitle, badge }} fields />` list on the left, the selected record on the right.
- `<Timeline records date="delivery_date" title subtitle badge meta groupBy="day" | "month" split />` grouped by date; upcoming first, then past.
- `<Calendar records date title badge />` month view with arrows.
- `<StatRow stats={[{ label, value, hint, tone, format: "number" | "money" | "percent" | "text", currency }]} />`, `<StatCard label value hint tone format currency />`.
- `<Chart type="bar" | "hbar" | "line" | "area" | "donut" data title description format currency height />` `data` is `[{ label, value }]` (from aggregate, countBy, byMonth). Several series: rows plus `x="month"` and `series={[{ key, label }]}` (at most 5).
- `<Dashboard stats={[...]} charts={[{ type, data, title, format }]}>…</Dashboard>` stats, then a grid of charts, then children.
- `<ViewTabs views={[{ id, label, content }]} defaultView toolbar />` switch between layouts of the same records; put the filter bar in `toolbar`.
- `useFilters(list, { search: true | [fields], facets: [fields], placeholder })` → `{ filtered, bar }`. Call it at the top of App, always render `bar` (as ViewTabs' `toolbar`, or above the block when there is no ViewTabs) and give `filtered` to the blocks.
- Lower level, when no block fits: `<RecordCard record card onOpen />`, `<FieldList record fields />`, `<Value record spec />`, `<RecordSheet record open onOpenChange />`, `useOpenRecord()` → `open(record)`.

## Primitives
`<Card title description footer onClick>`, `<Badge tone>`, `<StatusBadge value />`, `<Tag>`, `<Dot series={2} />`, `<Button variant="primary" | "secondary" | "ghost" | "link" size="sm" | "md" onClick>`, `<Input />`, `<SearchInput value onChange />`, `<Select value onChange options placeholder label />` (`""` = all), `<Tabs tabs={[{ id, label, content }]} toolbar />`, `<Sheet open onOpenChange title actions>`, `<Tooltip content>`, `<Avatar name />`, `<Progress value max />`, `<EmptyState title description />`, `<OpenEmail record variant="link" | "secondary" | "icon" />`.

## Example
```jsx
<script type="text/jsx">
function App({ data }) {
  const loans = records(data, "loan");
  const { filtered, bar } = useFilters(loans, { search: ["title", "branch"], facets: ["status"] });
  const overdue = loans.filter(l => l.status === "overdue").length;
  const card = { title: "title", subtitle: "branch", meta: [{ field: "due_date", label: "Due", format: "relative" }], badge: "status" };
  return (
    <Page title="Library loans" description="Books I have out and when they are due">
      <StatRow stats={[
        { label: "On loan", value: loans.filter(l => l.status !== "returned").length },
        { label: "Overdue", value: overdue, tone: overdue ? "danger" : "neutral", hint: overdue ? "Return these first" : undefined },
        { label: "Fines", value: sumBy(loans, "fine_amount"), format: "money", currency: "EUR" },
      ]} />
      <ViewTabs toolbar={bar} views={[
        { id: "board", label: "Board", content: <Board records={filtered} groupBy="status" columns={["borrowed", "renewed", "overdue", "returned"]} card={card} /> },
        { id: "due", label: "Due dates", content: <Timeline records={filtered} date="due_date" title="title" subtitle="branch" badge="status" /> },
        { id: "table", label: "All loans", content: <DataTable records={filtered} columns={["title", "branch", { field: "due_date", format: "date" }, "status", "fine_amount"]} /> },
      ]} />
    </Page>
  );
}
</script>
```
