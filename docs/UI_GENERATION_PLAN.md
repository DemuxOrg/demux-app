# UI generation v2 — plan

Status (2026-11-21): phases 0–5 are built; phase 6 (evals) is partly done (one real build checked, see §9). Implementation order is in §9. Where this file and `frontend/theme.md` disagree on UI, theme.md wins.

## 1. Why

Today the app phase writes about 300 lines of vanilla JS from scratch on every build and every edit (`backend/app/agent/prompts.py`, `APP` / `APP_CONTRACT`). The prompt forces the `--dmx-*` tokens and base classes (`frontend/theme.md` §10.3), so every app looks like Demux, and quality depends on how well a 27B model draws a whole UI in one go. Colours are a prompt rule only: nothing in `appcheck.py` enforces them.

Goals:
- A higher quality floor and fewer failed app checks, with fewer tokens per build and edit.
- The user chooses what the workspace shows; the look always stays on-brand.
- Vague prompts get clarified before the guide is written.
- The build screen tells the user where they are and when their part is done.

## 2. Principles

1. **The user decides what the workspace shows** (views, fields, grouping, filters, sorting, totals). **Demux decides how it looks** (palette from a fixed set, type, spacing, component styles).
2. **Every question has its recommended answer preselected**, so one press of Continue accepts it. A build never stalls for long on the user: no answer → the recommended option.
3. **The step count never goes up.** A step that is not needed ticks off instead of disappearing.
4. **The security model does not change.** `sandbox="allow-scripts"` iframe, CSP with no network, inline-only scripts, `write_app` checks. Everything new is inlined by the shell.
5. `theme.md` wins over code: every UI change below lands there first.

## 3. The new build flow

```
Prompt ─► design: searches ─► [ask_user?] ─► guide ─► propose_views ─► reading emails ─────► app phase ─► Ready
            │                    │                         │                                  ▲
 UI:   1. Your look         2. A few questions        3. Your layout ────────────────────────┘ (waits for the layout)
       (shown at once)         (only if needed)          4. Reading your emails · 5. Building your workspace
```

- **Look** is shown as soon as the user clicks Build. It needs nothing from the model and fills the ~15 s the design agent spends searching. The build never waits for it: the palette is applied by the shell, not by the generated code (§4).
- **Questions** come from the design agent after its first searches, only when the prompt is ambiguous (§6). The design phase waits for the answers.
- **Views** are proposed from the guide (§7). Mail reading starts as soon as the design phase ends, so it runs while the user picks; only the app phase waits for the choice.
- Clear prompt: Look → Layout. Ambiguous prompt: Look → Questions → Layout.
- Timeouts: 2 minutes per waiting point, then the recommended answers. The footer "You can close this page…" appears only once the user's part is done.

## 4. Palettes

- Five palettes, defined and contrast-checked in `theme.md` §10.3: Violet (default), Ocean, Teal, Rose, Graphite. No green, orange or red palette: they would read as the success, warning or danger status colours.
- **A palette changes only** the accent family (`--dmx-accent`, `-hover`, `-ink`, `-soft`, `-line`, `-tint`, `-ring`) and the chart series order (`--dmx-series-1…5`). Neutrals, ink, surfaces, lines, status pairs, `--dmx-cat-*`, font and radii never change. That is what keeps every choice on-brand.
- The shell holds every palette as `:root[data-palette="teal"]{…}`; `build_srcdoc(app_html, palette)` sets the attribute. The iframe (`AppFrame.tsx`) and the headless check use the same function.
- Stored in its own column, `workspaces.palette` (default `violet`), not in `config`: a running edit saves the whole `config` back (it would overwrite a palette chosen meanwhile), Undo restores `config`, and "Try again" clears it. Like the name, the palette is a user preference that Undo does not touch.
- **Chosen once, during the build** (setup step "Your look", §3), with the user. There is no palette switcher afterwards and the edit agent cannot change it: a chat request for other colours gets one sentence saying the look was set at build time.
- Enforcement: `appcheck.static_problems` rejects raw colours (hex, `rgb(`, `hsl(`, named colours in style values) in generated code. Stored apps are not re-checked; an edit of an old app has to remove them.
- Today's v1 apps already style through `--dmx-*` variables, so palettes work on them too and can ship before the kit (§9, phase 1).

## 5. Component kit (runtime v2)

The model stops drawing UI and composes blocks we built and tested.

**Packaging.** shadcn is source code (React + Tailwind + Radix), not a library the iframe can load. The kit is a package at `app-kit/` (repo root, so Next.js, its lint and its type check leave it alone) built with Vite into one JS file and one CSS file, committed under `backend/app/agent/kit/` (like `fonts/`), rebuilt with a new `make kit`. `shell.py` inlines both. Tailwind runs only at kit build time: the model never writes Tailwind classes. shadcn components are restyled to theme.md (pill buttons, radii, tokens), not shadcn defaults; shadcn's `--primary`, `--background`, … map to `--dmx-*`.

**Three layers**, exposed as globals:
- **Blocks** (the skeletons). They take records plus field mappings as props:

  | Block | Covers |
  |---|---|
  | `Board` | Kanban / Jira-style: columns by a field, card template (title, subtitle, badges, meta), counts, optional swimlanes. Read-only: no drag and drop. |
  | `DataTable` | Sort, search, facet filters, typed cells (money, date, status), row → `RecordSheet` |
  | `Dashboard`, `StatCard`, `Chart` | KPI row; bar, line, area, donut (shadcn charts / Recharts); recent items |
  | `Timeline` | Grouped by date, upcoming vs past |
  | `Calendar` | Month view of dated records |
  | `Gallery`, `ListDetail` | Card grid; list with a detail pane |
  | `RecordSheet` | Side panel: every field plus the source emails |
  | `ViewTabs`, `FilterBar`, `EmptyState` | Switching views, shared filters, no data yet |

- **Primitives** (shadcn): Card, Badge, Button, Tabs, Select, Input, Sheet, Dialog, Tooltip, Avatar, Progress, Separator, plus layout pieces `Stack`, `Row`, `Grid`, `Section`.
- **Helpers**: `records(data, type)`, money/date formatting, `groupBy`, `sum`, `count`, status → tone, `OpenEmail` (calls `demux.openSource`).

**Contract v2.** The model writes `function App({ data })` composing blocks; JS still computes derived values. The kit's runtime defines `render(data)` and mounts `App`, so the bridge (`demux:data`, `demux:rendered`, `demux:error`) and the Playwright smoke test keep working. A typical app should be 30–80 lines instead of ~300.

**Prompt reference.** Each block ships a short doc (props + one example). The kit build concatenates them into `kit/catalog.md`, which the APP and EDIT prompts include. It is generated from the kit, so it cannot drift. Target: under ~4k tokens.

**Gallery.** A dev-only frontend page renders every block with fixture data, to build and review them.

**Decided:** the model writes JSX (models write it far more reliably than `htm`); the kit compiles it in the iframe with Sucrase and runs it as an inline script, so the CSP needs no `unsafe-eval`. React 19 (not Preact). Size: kit.js ≈ 1.05 MB (≈ 300 KB gzipped), kit.css ≈ 23 KB; `/app-shell?runtime=v2` is gzipped to ≈ 360 KB and fetched once per page. Which shell an app gets is decided by its HTML (`app_runtime`: a `<script type="text/jsx">` is v2), so no database column is needed.

## 6. Clarifying questions (`ask_user`)

- A design-phase tool, callable **once**, after the first `search_mail` calls, so questions are grounded in the mailbox ("I found orders from Amazon, Zalando and Uber Eats. Should food deliveries count?").
- Input: 1–3 questions, each with 2–4 options, a recommended option, and "Other" free text allowed. All shown on one card; one round, no back-and-forth.
- Rules in `DESIGN`: ask only when the answer changes which emails count, which record types exist or which fields are tracked. Never ask what the mailbox can answer. Never ask about look or layout. Clear prompts ask nothing.
- Mechanics: the build's setup lives in the run's `input` JSON, one key per fact (`questions`, `questions_state`, `answers`, `layout_options`, `layout_primary`, `layout_state`, `layout`, `look`). The worker writes its keys through the persister and `POST /workspaces/{id}/setup` writes the user's; both use `input || {key: value}`, so neither overwrites the other. The tool polls for `answers` every 1.5 s up to `SETUP_WAIT_SECONDS` (120), then returns the answers or the recommended options. CLI and eval runs do not wait.
- The questions and answers are saved in `workspaces.config.clarifications`; the design agent writes them into the guide, and `edit_input` includes them, so later edits remember them.

## 7. View options (`propose_views`)

- A design-phase tool called after `write_guide`: 2–5 options, each naming a kit block, a title tied to the data ("Board by status", "Timeline by delivery date", "Totals: in transit, delayed, delivered this month") and whether it is recommended; plus the recommended first view.
- The frontend shows a small static thumbnail per block kind next to the model's title. The user ticks the ones they want and picks the one that opens first.
- In the UI these are *layouts* (theme.md §11 vocabulary); `views` is only the internal name.
- Saved in `workspaces.config.layout` (`views` + `primary`). The app phase waits for them (or the timeout), then gets them as a `<layout>` block in `app_input`. This narrows the app phase, so it also makes the generated app more reliable.

## 8. Progress screen

Replaces `BuildProgress.tsx` (theme.md §7.10 redesigned first):

1. Your look
2. A few questions (ticks off if none)
3. Your layout
4. Reading your emails
5. Building your workspace

- "Step 3 of 5" and a segmented bar. The total never changes.
- After step 3: "That's everything we need from you. You can close this page; your workspace will be ready here."
- Real numbers only: "48 of 120 threads read · 14 shipments found so far".
- "Almost there" only on step 5.
- The short wait between questions and views says what is happening ("Preparing options from your emails"), so the screen never looks frozen.
- Reading progress is structured: process events carry `done` / `total` threads. The setup comes with the active run (`active_run.setup`), and records found come from `record_counts`. `BuildFlow.tsx` replaces `BuildProgress.tsx`.
- Copy follows theme.md §11: "workspace", never "dashboard" ("How should your workspace look?").

## 9. Phases

Each phase ships on its own.

0. **theme.md.** *Done 2026-11-21:* palettes with contrast and the kit rules (§10.3), the build flow with its five steps (§7.10), motion (§9), copy and vocabulary (§11), Do/Don't (§12).
1. **Palettes in the shell.** *Done 2026-11-21:* the five palettes as shell CSS (also applied live through the `demux:palette` bridge message), the `workspaces.palette` column, the palette list in `/app-shell`, the raw-colour check. A ⋯ → Look switcher and a chat `set_palette` tool were built and then removed: the look is decided with the user during setup only. Nothing a user sees after a prompt changes until phases 3–5.
2. **Kit spike.** *Done:* folded into phase 3 (decisions in §5).
3. **Kit.** *Done:* every block and primitive, `catalog.md` (checked against the exports at build time), the gallery (`app/agent/gallery.py`), `make kit`.
4. **v2 generation.** *Done:* APP/EDIT prompts with the catalog, v2 checks (`function App`, no `<style>`, no `dangerouslySetInnerHTML`, no imports, no raw colours), v1 apps keep their shell, the fallback app is a kit app. Edits rewrite a v1 app as a kit app when they touch the interface.
5. **Setup flow.** *Done:* look step, `ask_user`, `propose_views`, the two waiting points with timeouts, `POST /workspaces/{id}/setup`, structured progress, `BuildFlow.tsx`.
6. **Evals.** *Partly done:* scenario 04 built through the CLI with the kit prompt: the app passed every check first time ($0.07 for the build). To do: run all 8 scenarios before and after (failed checks, tokens, build time, cost), add 2–3 vague-prompt scenarios, and check that the 8 clear ones ask nothing.

## 10. Later, not in this plan

- Show the workspace as soon as its interface exists and let it fill in while emails are read (the final check can still rebuild the interface, so it needs care).
- User overrides on records (for example dragging a card to another column): the data is read-only from email today.
- Leaving the build page early: skip the timeouts once nobody is watching (needs a presence signal).
