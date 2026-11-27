# UI generation v2 — plan

Status (2026-11-21): phases 0–5 are built; phase 6 (evals) is partly done (one real build checked, see §9). Implementation order is in §9. Where this file and `frontend/theme.md` disagree on UI, theme.md wins.

**Change (2026-11-26):** the build no longer has a look step (palette tiles) or a layout step (`propose_views`). Users found them generic: the same palette and layout questions on every build. The build screen has three steps (theme.md §7.10): the design agent asks one multiple-choice question per gap in the prompt (none for a precise prompt, up to five for a vague one, never about colours or style), then emails are read and the app is built. The answers reach the app phase as `<clarifications>`, so they also shape the interface. Workspaces keep the default `violet` palette. §3, §4 (“chosen once, during the build”), §6 and §7 below describe the earlier flow.

**Change (2026-11-27):** the component kit is no longer given to the model that writes apps. A dedicated UI model (GLM-5.2) designs the experience and the look of every new app; see §11. §4 (palettes) and §5 (the kit) now apply only to older v1/v2 apps.

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

## 11. Generative interfaces: the interface designer (v3, 2026-11-27)

**Why.** Composing a fixed kit made every workspace look the same (a white dashboard in one of five palettes), and Qwen3.8-27B is a weak designer. Now a model chosen for design quality designs every interface from scratch.

**Who does what.**
- **Qwen3.8-27B** (`BUILD_MODEL`) keeps the data work: questions, guide, Gmail searches, reading emails, edits to records. It never writes interface code.
- **GLM-5.2** (`UI_MODEL`, the interface designer, `app/agent/designer.py`) designs the UX (what comes first, structure, navigation, interactions, states) and the UI (palette, type, layout, motion), and writes the app. Picked because it ranked first on Design Arena's single-turn web design board in June 2026; the setting can point at any OpenAI-compatible chat model.

**Build.** While emails are read, the designer gets the facts only: the workspace name, the request, the user's answers to the questions (`<clarifications>`), the guide, and a data sample (6 records per type plus counts). Qwen writes no brief: the designer decides the experience itself. After reading, the app is checked against the real records; if it fails, the designer gets its app and the problems back. If the designer fails three times (or is unreachable) the build ends with the default app (a plain searchable list, also a studio app), and the user can ask for a redesign.

**Edits.** The chat agent (Qwen) gets `change_interface(change)` instead of `write_app`. The designer receives the current app, the change and the user's message verbatim, and returns the whole new app. Qwen no longer sees app code in its prompt. A change to an older v1/v2 app makes the designer rebuild it as a studio app.

**How it is called.** One plain chat without tools (any model can do it): the answer is one ```jsx block. `extract_app` takes the largest code block and drops harmless habits (imports of the globals, `export default`). The app is checked (`appcheck`: no network, no forbidden APIs, renders, shows the data, survives empty data, idempotent); problems go back to the model, up to `UI_MAX_ATTEMPTS` (3) answers in all. A cut-off answer (max tokens) asks for a shorter app. Calls use `UI_MAX_TOKENS` (40k: GLM reasons before it writes), `UI_CALL_TIMEOUT_S` (300 s), `UI_TEMPERATURE` (0.7) and `UI_FALLBACK_MODEL` (the same model on another provider, so a build never quietly falls back to a weaker designer). The default provider is Together (a steady ~375 tok/s; CoreWeave, the fallback, varied 225–335; DeepInfra ~90; measured 2026-11-27), with `UI_REASONING_EFFORT=none`: GLM writes without hidden reasoning, about half the tokens and twice as fast ("low" made no difference on Together). Set it to empty to restore reasoning. Every call goes through `MeteredLLM` in the `app` (build) or `edit` phase; prices are in `prices.yaml`.

**Runtime v3 (studio).** The stored app is `<script type="text/jsx" data-runtime="v3">…</script>` (`studio_app()`); `app_runtime()` tells v3, v2 and v1 apart, and `/app-shell?runtime=v3` serves its shell. The shell inlines:
- `kit/studio.js` (from `app-kit/src/studio.tsx`, about 310 KB gzipped): React 19 and its hooks, `cx`, Recharts (namespace and the common parts), `Icon` (about 180 lucide icons by name), `records`, `types`, `openEmail`, and the JSX compile + render shared with the kit (`runtime.tsx`).
- `kit/tailwind.js`: Tailwind v4's browser build, which compiles the app's class names in the iframe (no eval, so the CSP is unchanged). `dark:` follows a `dark` class only.
- Embedded fonts (`kit/fonts`, SIL OFL): Inter, Space Grotesk, Fraunces, Instrument Serif, JetBrains Mono, as `font-sans`, `font-display`, `font-serif`, `font-editorial`, `font-mono`.
- No Demux tokens, palettes or base classes. `studio.md` is the designer's reference and is checked against the exports at build time.

**Not changed.** The sandbox (`allow-scripts` only), the CSP (no network), the bridge, the headless check, older apps (v1/v2 keep their shells and palettes).

**To do.** Run the eval scenarios through the designer and compare against the kit (failed checks, cost, time, and screenshots side by side); compare interface quality with and without reasoning (`UI_REASONING_EFFORT`), and try GLM-5.3 if the router serves it.

## 12. Live build and question moments (2026-11-27)

Replaces the build progress card (§8) and changes how clarifying questions are collected (§6). The spec is `frontend/theme.md` §7.10 (live build) and §7.15 (question moment).

**What the user sees.** The build is the loading screen: a strip of real facts ("Reading your emails · 48 of 120 threads · 14 invoices found", a reading bar, Cancel) above the app panel, which shows the logo until the first record, then the preview app (`DEFAULT_APP`, served by `GET /app` with `provisional: true` while no app is saved) filling in. Records are paced one by one on the client (`useRecordDrip`, 300 ms per change) and marked in the app (`changedClass`, `CountUp` in the studio runtime). The generated app replaces the preview once, through a hidden second frame and a 300 ms crossfade (`LiveFrame`); the same frame stays when the build ends.

**Question moments.** One question at a time on a dimmed screen: first the **look** (unless the prompt names one: `app/agent/look.py`, plain code), then each clarifying question in the agent's order. One `POST /setup` per answer (`answers` merge, `answered_at` per answer; `look` for the look). The look's answer goes to the interface designer as `<look>`; Demux's palettes are not used. There is no layout moment (§7 was removed when the designer took over the structure).

**The agent doesn't wait for the screen.** `ask_user` returns at once; the agent may keep exploring, and `get_answers` (required before `write_guide`) waits until every question is answered or the user has been idle `SETUP_WAIT_SECONDS` since the question or their last answer. The designer waits for the look the same way, while the emails are read in parallel.

**Cost rules.** No new LLM call (look detection is code, pacing and diffs are client-side), no new transport (the 2 s poll while a run is active), at most ~3 frame posts a second, one app swap per build.
