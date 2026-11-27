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

## Icon names

activity, alarm-clock, archive, arrow-down, arrow-down-right, arrow-left, arrow-right, arrow-up, arrow-up-right, at-sign, award, baby, banknote, bed, bell, book, book-open, bookmark, box, briefcase, building-2, bus, calendar, calendar-check, calendar-clock, calendar-days, car, chart-bar, chart-line, chart-pie, check, check-check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-up-down, circle-alert, circle-check, circle-dashed, circle-dot, circle-x, clipboard, clipboard-list, clock, cloud, code, coffee, coins, compass, copy, credit-card, database, dollar-sign, dumbbell, ellipsis, euro, external-link, eye, eye-off, file, file-text, film, filter, flag, flame, folder, gift, globe, graduation-cap, hash, heart, heart-pulse, history, hotel, hourglass, house, image, inbox, info, key, landmark, laptop, layers, layout-dashboard, layout-grid, layout-list, leaf, link, list, list-checks, list-todo, loader-circle, lock, mail, mail-open, map, map-pin, maximize-2, menu, message-square, minus, monitor, moon, music, package, package-check, paperclip, pencil, percent, phone, piggy-bank, pill, pin, plane, plus, receipt, refresh-cw, repeat, rocket, rotate-ccw, scale, search, send, settings, share-2, shield, shield-check, ship, shirt, shopping-bag, shopping-cart, sigma, sliders-horizontal, smartphone, sparkles, square-kanban, star, stethoscope, store, sun, table, tag, target, ticket, timer, train, trending-down, trending-up, triangle-alert, trophy, truck, user, user-check, users, utensils, wallet, wrench, x, zap
