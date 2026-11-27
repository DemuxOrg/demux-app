# Studio runtime reference

Your app runs in a sandboxed iframe with no network. Nothing can be imported or loaded:
everything below is already a global. Anything not listed here does not exist.

## Styling

- **Tailwind CSS v4** compiles your class names in the page (the full default theme:
  colours, spacing, radii, shadows, gradients, `backdrop-blur`, animations). `dark:`
  applies only inside an element with the class `dark`: the user's system setting is ignored.
  Arbitrary values work (`bg-[#0f172a]`, `grid-cols-[2fr_1fr]`, `shadow-[0_8px_30px_rgb(0,0,0,0.12)]`).
- You may also render one `<style>{`...`}</style>` element inside your JSX for keyframes,
  custom properties or anything Tailwind cannot express. No `@import`, no `url(http…)`.
- **Fonts** (embedded; nothing else loads):
  - `font-sans`: Inter (variable, 100–900), the default
  - `font-display`: Space Grotesk (variable, 300–700)
  - `font-serif`: Fraunces (variable, 100–900)
  - `font-editorial`: Instrument Serif (400, normal and italic)
  - `font-mono`: JetBrains Mono (variable, 100–800)
- The page starts blank: no background colour and no padding. You own the whole canvas.

## React

`React`, `Fragment`, `useState`, `useMemo`, `useEffect`, `useLayoutEffect`, `useRef`,
`useCallback`, `useReducer`, `useId`, `useTransition`, `useDeferredValue`: React 19.
Write `<>…</>` or `<Fragment>` for fragments.

`cx(...classes)`: joins class names, skipping falsy ones (clsx):
`cx("rounded-xl px-3", active && "bg-slate-900 text-white")`.

## Charts (Recharts 3)

Globals: `ResponsiveContainer`, `BarChart`, `Bar`, `LineChart`, `Line`, `AreaChart`, `Area`,
`ComposedChart`, `PieChart`, `Pie`, `Cell`, `RadialBarChart`, `RadialBar`, `RadarChart`,
`Radar`, `PolarGrid`, `PolarAngleAxis`, `PolarRadiusAxis`, `ScatterChart`, `Scatter`,
`Treemap`, `XAxis`, `YAxis`, `CartesianGrid`, `Tooltip`, `Legend`, `ReferenceLine`,
`LabelList`. Anything else from Recharts: `Recharts.Brush`, `Recharts.Funnel`…

Always wrap a chart in `<ResponsiveContainer width="100%" height={240}>`. Colours are
plain props (`fill="#6366f1"`, `stroke="currentColor"`); gradients go in `<defs>`.

## Icons

`<Icon name="calendar-days" size={16} className="text-slate-500" />`: a lucide icon by
kebab-case name, stroke 1.75 by default. An unknown name renders nothing. The names are
listed at the end of this file.

## Data

`App({ data })` receives the whole data document:
`{ "<record_type>": { "<record_id>": { ...fields, "_sources": [...], "_updated_at": "…" } } }`.

- `records(data, "type")`: the records of one type as an array, each with its `id`.
  A missing type gives `[]`.
- `types(data)`: the record type names present.
- `openEmail(record)`: opens the record's latest source email in Gmail (in a new tab).
- `demux.openLink(url)`: asks the user, then opens an https link in a new tab.

Fields come from email: any of them can be missing, null or of an unexpected type.
Dates are ISO strings (`2026-03-02` or `2026-03-02T10:00:00Z`). Money is a number with a
separate currency field (ISO code); format it with `Intl.NumberFormat`.

## Live changes

Records arrive and change while the user watches (during the build and every sync).

- `changedClass(type, id)`: `"demux-new"`, `"demux-updated"` or `""` for about 1.6 s after
  that record arrived or changed. Put it on each record's row or card:
  `<li className={cx("…", changedClass("invoice", r.id))}>`. Both classes are styled for you
  (a soft ring in the current text colour, and a short rise for new records); don't
  restyle them.
- `<CountUp value={total} format={(n) => money(n)} />`: a number that counts up from its
  previous value when it changes (400 ms, tabular). Use it for headline numbers. `format`
  gets the in-between values too, so it must accept any number.

Both do nothing when the user prefers reduced motion.
