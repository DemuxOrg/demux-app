# Demux — Design System

> Context file for Claude Code. Read this before building or changing any UI in Demux.
> Source of truth for colors, type, components and copy. If code and this file disagree, this file wins. Change this file first, then the code.
> Visual reference: "Demux — Product Design" canvas (Prompt → Workspace → Result, plus a Colors & type sheet).

---

## 1. Principles (apply to every screen)

1. **One idea per screen.** Each screen has one focal element and one primary action. If a screen needs two primary buttons, it needs two screens.
2. **Sky behind, white in front.** The sky gradient is only a backdrop. Content always sits on white (or translucent white) surfaces.
3. **The logo colors mean "Demux is acting".** Violet, magenta and coral mark actions, focus, selection, live updates and build progress. They are never decoration.
4. **The full logo gradient appears at most once per screen.** Today that is only the logo.
5. **Calm, not "AI".** No sparkles, no glow orbs, no gradient text, no neon, no emoji, no "AI-powered" badges, no bento grids of feature icons, no left-border accent cards.
6. **Real content.** Concrete names, amounts and dates. Never lorem ipsum, and never invented stats in product UI.
7. **Accessible as built.** Real `<button>`, `<a>`, `<input>` + `<label>`. Hit targets ≥ 44px. Text contrast ≥ 4.5:1 (§3.6).

---

## 2. Logo

- **Mark:** a white circle with a violet → pink gradient ring and three blades fanning out from one point on the left (violet on top, magenta in the middle, coral at the bottom). One input, many outputs: demultiplexing.
- **Wordmark:** "Demux" in Instrument Sans 600, letter-spacing −0.02em, ink `#0C1A2E`.
- **Lockup:** mark + wordmark, gap = 0.35 × mark size (28px mark → 10px gap, 19px wordmark; 32px mark → 11px gap, 22px wordmark).
- **Sizes:** 28px in the login header and the app drawer, 42–56px in prompt and build cards, 64px+ for hero or empty states. Minimum 20px.
- **Clear space:** at least ¼ of the mark's diameter on every side.
- **Never:** recolor it, put it on a gradient other than its own, add glow or drop shadow, rotate it, or set the wordmark in another font.
- **On sky:** use the mark as is (it has its own white disc). On dark: same.

`public/brand/logo-mark.svg` (vector redrawn from the launch video. **Replace it with the official file when available.**)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <defs>
    <linearGradient id="ring" x1="0.35" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="#7A35E6"/><stop offset="0.55" stop-color="#B83FAF"/><stop offset="1" stop-color="#E04E72"/>
    </linearGradient>
    <linearGradient id="b1" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#8A3FE8"/><stop offset="1" stop-color="#5B3BF0"/></linearGradient>
    <linearGradient id="b2" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9B3FD0"/><stop offset="1" stop-color="#DE3773"/></linearGradient>
    <linearGradient id="b3" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#D2477A"/><stop offset="1" stop-color="#F26A3A"/></linearGradient>
  </defs>
  <circle cx="50" cy="50" r="43.5" fill="#FFFFFF" stroke="url(#ring)" stroke-width="4.6"/>
  <path d="M29 52 L63.2 62.2 Q67.8 63.8 67.2 69.4 Q66.5 74.6 61.8 72.8 Z" fill="url(#b3)"/>
  <path d="M29 51.5 L66.6 45.6 Q71.4 45 71.4 51.4 Q71.4 57.8 66.6 57.4 Z" fill="url(#b2)"/>
  <path d="M29 51 L60.8 29.6 Q65.4 26.8 66.9 31.4 Q68 35.6 64.6 38.8 Z" fill="url(#b1)"/>
</svg>
```

If the mark is inlined more than once on the same page, give each copy unique gradient ids.

---

## 3. Color

### 3.1 Primary: Sky (backgrounds only)
Sampled from the launch-video background. Use it for page backdrops and nothing else: no buttons, no text, no borders.

| Token | Hex | Use |
|---|---|---|
| `sky-deep` | `#3F92F0` | Deepest corner of the gradient |
| `sky-500` | `#5EA7F4` | Main gradient blob |
| `sky-300` | `#8DBDEE` | Gradient base color |
| `sky-200` | `#A9CBF0` | Disabled/idle send button on white (decorative) |
| `haze` | `#CAD7E8` | Soft light area in the gradient |
| `mist` | `#DFE2E7` | Whitest haze in the gradient |

### 3.2 Secondary: Logo (actions and live states)

| Token | Hex | Use |
|---|---|---|
| `violet` | `#6A3DF0` | Primary buttons, links on white, focus ring, text caret, selected state, "new" dots |
| `violet-hover` | `#5A2FDC` | Hover/pressed for violet buttons |
| `violet-ink` | `#4B24C9` | Text on `violet-soft` (chips, "Updated" tags, "Building" status) |
| `violet-soft` | `#EEE9FE` | Background for selected/updated/building states, done-step icon |
| `violet-line` | `#C9BCFB` | Border of a just-updated record |
| `violet-tint` | `#FBFAFF` | Background of a just-updated record |
| `magenta` | `#D63A7C` | Work in progress (spinner arc, "reading" phase). Never for small text on white |
| `magenta-soft` | `#FCE3EC` | Spinner track, magenta tints |
| `coral` | `#EE5A44` | Gradient end only. Never alone, never for text |

**Brand gradient** (logo colors). Only for the logo and build progress:
```css
--gradient-brand: linear-gradient(90deg, #6A3DF0 0%, #D63A7C 60%, #EE5A44 100%);
```

### 3.3 Neutrals: ink and surfaces

| Token | Hex | Use |
|---|---|---|
| `ink` | `#0C1A2E` | Primary text everywhere; headlines on sky; dark CTA (marketing) |
| `ink-2` | `#33445C` | Secondary text on white |
| `ink-3` | `#5B6B80` | Meta text, placeholders, column headers on white |
| `ink-on-sky` | `#172741` | Secondary text placed directly on the sky gradient |
| `line` | `#E6EBF2` | Card borders, dividers |
| `line-soft` | `#EDF1F6` | Row dividers inside cards |
| `surface` | `#FFFFFF` | Cards, panels, generated apps |
| `surface-2` | `#F4F7FB` | Board columns, quiet wells |
| `surface-3` | `#F5F7FB` | Chip background |
| `tag` | `#F1F4F8` | Neutral tag background |
| `glass` | `rgba(255,255,255,0.72)` | Translucent cards/panels on sky (with blur 18–20px) |
| `glass-strong` | `rgba(255,255,255,0.60)` | Icon buttons and secondary pills on sky |
| `glass-border` | `rgba(255,255,255,0.85)` | Border of glass cards |
| `line-on-glass` | `rgba(12,26,46,0.08)` | Dividers inside glass panels |

### 3.4 Status (records inside workspaces)
Always use the pair: soft background + dark foreground.

| Status | Background | Text | Example |
|---|---|---|---|
| `success` | `#E4F5EA` | `#1D6B37` | Paid, Approved, Delivered |
| `danger` | `#FDECEA` | `#A8321F` | Overdue |
| `warning` | `#FFF1E2` | `#8F4405` | Delayed, Waiting on brief |
| `info` | `#E6F0FD` | `#1F5FB8` | In transit, Invoice sent |
| `neutral` | `#EEF2F7` | `#33445C` | Unpaid, Booked, Waiting for approval |
| `live` dot | `#2FB36B` | — | "Synced 3 min ago", "Live from your inbox" |

**Category dots** (columns, clients), 6–7px circles: `#5EA7F4` blue · `#9A8BF7` lavender · `#E0679A` pink · `#2FB36B` green · `#F5A524` amber · `#9A7BF7` purple. Dots are always paired with a text label: never color alone. Inside v1/v2 generated apps, dots and chart series follow the palette's series order (§10.3); studio apps choose their own.

### 3.5 Dark surfaces (marketing/video only, not the MVP app)
From the board in the launch video: board `#16171A`, column `#1F2024`, card `#2A2B30`, tag `#36373D`, text `#ECEDEF` / `#F3F4F6`, muted `#A3A7AF`, faint `#8E929B`, success text `#6BDB8C` on `rgba(52,199,89,0.16)`, live dot `#34C759`.

### 3.6 Contrast (checked, WCAG 2.x)

| Pair | Ratio | Verdict |
|---|---|---|
| ink on white | 17.5 | ✓ any |
| ink-2 on white | 9.9 | ✓ any |
| ink-3 on white | 5.4 | ✓ any (≥12px) |
| ink-3 on surface-2 | 5.1 | ✓ |
| ink on sky-500 | 6.9 | ✓ |
| ink-on-sky on sky-500 / sky-deep | 5.9 / 4.7 | ✓ |
| white on violet | 5.9 | ✓ buttons |
| violet on white | 5.9 | ✓ links |
| violet-ink on violet-soft | 7.4 | ✓ |
| white on magenta | 4.4 | ✗ body text; only large text (≥ 19px bold or ≥ 24px) |
| white on coral | 3.4 | ✗ never put text on coral |
| **white on any sky** | **2.5** | **✗ never put white text on the sky** |
| status pairs (§3.4) | 5.4–8.8 | ✓ |
| generated-app palettes (§10.3) | 5.5–14.4 | ✓ |

---

## 4. Backgrounds

### 4.1 Sky gradient (app pages, full screen)
```css
.bg-sky {
  background-color: #8DBDEE;
  background-image:
    radial-gradient(70% 70% at 6% 0%,   rgba(86,162,244,.95),  rgba(86,162,244,0) 70%),
    radial-gradient(55% 60% at 100% 4%, rgba(112,178,247,.90), rgba(112,178,247,0) 70%),
    radial-gradient(50% 50% at 86% 78%, rgba(208,220,234,.95), rgba(208,220,234,0) 70%),
    radial-gradient(45% 50% at 4% 100%, rgba(226,230,236,.95), rgba(226,230,236,0) 70%),
    radial-gradient(40% 45% at 100% 100%, rgba(72,152,242,.85), rgba(72,152,242,0) 70%);
}
```
Vary the blob positions slightly between screens (mirror horizontally, for example) so pages don't look identical. Keep the same five colors.

The sky is painted on a fixed, **still** layer behind the grain (`.dmx-sky` in the root layout). It never animates: a full-screen layer that moves forces the browser to repaint and re-blend the whole viewport (grain included) on every frame, which measured at 15–25 fps on every page. The `body` keeps the plain `bg-sky` as its fallback.

### 4.2 Grain (always on top of the sky, under content)
Grain keeps the gradient from looking like a flat CSS wash.
```css
.bg-grain::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.35'/%3E%3C/svg%3E");
  background-size: 256px 256px;
  mix-blend-mode: soft-light;
  opacity: .6;
}
```
Content above the grain gets `position: relative; z-index: 1`. The grain should be barely visible. If you notice it at first glance, lower the opacity.

---

## 5. Typography

- **Family:** Instrument Sans (Google Fonts), one family only. Weights **400, 500, 600**. No 700, no italics in the UI.
- **Fallback:** `-apple-system, "Helvetica Neue", Arial, sans-serif`.
- Large type is **500 with negative tracking**, not bold. Bold (600) is for small titles, labels and names.
- Numbers in tables, amounts and counters: `font-variant-numeric: tabular-nums`.
- Headlines: `text-wrap: balance`. Paragraphs: `text-wrap: pretty`.
- Sentence case everywhere. No ALL CAPS labels, no eyebrow labels above headlines.

| Style | Size / line-height | Weight | Tracking | Use |
|---|---|---|---|---|
| `display` | clamp(46px, 6.6vw, 96px) / 0.98 | 500 | −0.042em | Marketing hero only |
| `title-xl` | clamp(32px, 3.4vw, 46px) / 1.06 | 500 | −0.035em | Page question ("What do you want to see from your inbox?") |
| `title-lg` | 30px / 1.1 | 500 | −0.03em | Card headline ("Building your workspace") |
| `heading` | 24px / 1.2 | 600 | −0.02em | Workspace title inside the app panel |
| `prompt` | 22px / 1.4 | 400 | −0.01em | Prompt textarea |
| `title-sm` | 18px / 1.3 | 600 | −0.015em | Top-bar workspace name |
| `item` | 15–16px / 1.35 | 600 | 0 | Record titles, list item titles |
| `body` | 16px / 1.5 | 400 | 0 | Paragraphs |
| `ui` | 14–15px / 1 | 500 | 0 | Buttons, tabs, chips |
| `meta` | 13px / 1.45 | 400 | 0 | Timestamps, client names, captions |
| `micro` | 12px / 1.4 | 400–500 | 0 | Tags, status pills |

---

## 6. Space, radius, elevation

**Spacing scale (px):** 4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28 · 32 · 36 · 40 · 48 · 56 · 64 · 72 · 96. Lay out groups with flex/grid `gap`, not margins.

**Radius**

| Token | Value | Use |
|---|---|---|
| `tag` | 6px | Tags inside records |
| `sm` | 12px | Record cards |
| `md` | 16px | Board columns |
| `lg` | 20px | Glass cards, workspace cards, ask input |
| `xl` | 26px | App panel, side panel |
| `2xl` | 30px | Prompt card, build card (hero white cards) |
| `full` | 999px | Buttons, chips, segmented controls, status chips, avatars |

In Tailwind these map to `rounded-tag`, `rounded-sm` … `rounded-2xl`, `rounded-full` (§10.2 overrides the defaults).

**Shadows** (always tinted blue `rgb(22,62,128)`, never pure black)
```css
--shadow-float: 0 50px 90px -40px rgba(22,62,128,.55), 0 2px 8px rgba(22,62,128,.06); /* hero cards on sky */
--shadow-panel: 0 40px 80px -40px rgba(22,62,128,.50), 0 2px 6px rgba(22,62,128,.05); /* app panel */
--shadow-glass: 0 20px 40px -28px rgba(22,62,128,.50);                                  /* glass cards */
--shadow-pill:  0 6px 14px -8px rgba(22,62,128,.50);                                    /* selected segment */
--shadow-input: 0 10px 24px -16px rgba(22,62,128,.45);                                   /* ask input */
--shadow-dark:  0 60px 110px -50px rgba(12,26,46,.75);                                   /* dark board (marketing) */
```

**Glass:** `background: rgba(255,255,255,.72); border: 1px solid rgba(255,255,255,.85); backdrop-filter: blur(20px);`

---

## 7. Components

Tailwind recipes assume the tokens in §10.

### 7.1 Buttons

| Variant | Spec | Tailwind |
|---|---|---|
| **Primary** (Build, Send, Join) | height 48px (height 44px in panels), px 20–22, radius full, `violet` bg, white 16px/500, optional trailing arrow 18px | `inline-flex items-center gap-2 h-12 px-[22px] rounded-full bg-violet text-white text-base font-medium hover:bg-violet-hover` |
| **Secondary on sky** | height 44px, px 16, radius full, `glass-strong` bg, ink 14px/500, leading icon 16px | `inline-flex items-center gap-2 h-11 px-4 rounded-full bg-white/60 text-ink text-sm font-medium hover:bg-white/90` |
| **Icon button on sky** (back, more, account) | 44 × 44px circle, `glass-strong`, icon 18–20px ink, `aria-label` required | `grid place-items-center size-11 rounded-full bg-white/60 hover:bg-white/90` |
| **Ghost icon** (rename) | 44 × 44px circle, transparent, icon 16px `ink-on-sky` | `grid place-items-center size-11 rounded-full hover:bg-white/60` |
| **Send (square)** | 44 × 44px, radius 14, violet, white arrow-up | `grid place-items-center size-11 rounded-[14px] bg-violet` |
| **Dark CTA** (marketing only) | height 54px, px 28, radius full, `ink` bg, white | `h-[54px] px-7 rounded-full bg-ink text-white` |

States for all buttons:
- **Focus:** `outline: none; box-shadow: 0 0 0 3px rgba(106,61,240,.22)` (`focus-visible:ring-[3px] focus-visible:ring-violet/25`)
- **Disabled:** opacity .4, no hover, `cursor: not-allowed`
- **Loading:** keep the width, replace the label with a 16px spinner (§9)
- One primary (violet) button per screen.

### 7.2 Prompt card (the signature component)
- White, radius 30, padding 24/24/18, `shadow-float`, max-width 760.
- Row: logo mark 46px + `<textarea>` (prompt style 22px, no border, `caret-color: #6A3DF0`, placeholder `ink-3`: "Describe what you want to keep track of…").
- Footer row: two example chips on the left ("Unpaid invoices and who I owe", "Job applications by stage"; short enough to share one row with Build from 640px), primary **Build →** on the right.
- Focus: no ring and no movement on the card; the violet caret is the focus cue.
- Keyboard: Enter builds, Shift+Enter adds a new line.

### 7.3 Chips (example prompts)
height 36px, px 14, radius full, bg `surface-3`, 1px `#E3E8F0` border, `ink-2` 14px/500. Hover: bg `violet-soft`, text `violet-ink`, border `#DCD2FD`. Clicking one fills the prompt.

### 7.4 Inputs
- **Ask for a change:** white, radius 20, padding 6/6/6/16, `shadow-input`, input 44px tall with 15px text, square violet send button. No focus ring, like the prompt card.
- **Email field (marketing):** white pill, radius 30, padding 6, input 52px tall with 16px text + dark CTA inside.
- Every input has a `<label>` (visually hidden if needed).

### 7.5 Segmented control / tabs
Track: radius full, padding 4, gap 4, bg `rgba(255,255,255,.5)` on sky or `rgba(12,26,46,.06)` on glass. Segment: height 38–44px, radius full, 14–15px/500. Selected: white bg, ink text, `shadow-pill`. Unselected: transparent, `ink-2`. Use `role="tablist"` / `aria-selected`.

### 7.6 Status chip (top bar)
height 30px, px 12, radius full, 13px/500, 7px dot.
- Building: bg `violet-soft`, text `violet-ink`, dot `violet` pulsing.
- Failed: bg `#FDECEA`, text `#A8321F`.
- Ready: no chip. Show "● Synced 3 min ago" as plain `ink-on-sky` text with a `#2FB36B` dot.

### 7.7 Tags and status pills
- **Tag** (inside records): radius 6, padding 3/7, 12px, bg `tag`, text `ink-2` ("Due Dec 2").
- **Status pill** (tables): height 22–26px, px 8–10, radius full, 12–13px/500, §3.4 pairs.
- **Updated tag:** bg `violet-soft`, text `violet-ink`, 5px violet dot, "Updated 2 min ago".

### 7.8 Cards
- **Workspace card (list):** glass, radius 20, padding 16/18, `shadow-glass`, hover lift (§9, `dmx-lift`). Title 16/600, meta 13 `ink-2` with live dot ("Synced 3 min ago · 14 invoices"), chevron right.
- **Empty slot:** min-h 72, radius 20, 1.5px dashed `rgba(12,26,46,.22)`, centered 14px `ink-on-sky` ("One more slot free").
- **Record card (board):** white, radius 12, padding 12/14, 1px `line`. Title 15/600 · client row 13 `ink-3` with 6px dot · tag.
- **Just-updated record:** bg `violet-tint`, border `violet-line`, `box-shadow: 0 0 0 3px rgba(106,61,240,.08)`, plus the Updated tag. The highlight stays until the user has seen it (page focus + 10s), then fades over 600ms.
- **Board column:** bg `surface-2`, radius 16, padding 12, gap 8. Header 13/500 `ink-2` + dot + count in `ink-3`.

### 7.9 Activity item (side panel)
*Hidden for now, like the side panel itself (§8.4). Kept for when they return.*
Vertical list with dividers `line-on-glass`, padding 14px 0:
1. Time, 12px `ink-2` (newest item gets a 6px violet dot)
2. Record title, 15/600
3. Change: `from` pill (neutral) → arrow 14px `ink-3` → `to` pill (status color), or one sentence 13px `ink-2`
4. Source link: mail icon 14px + "Sender · “subject or quote”" 13px `ink-2`. Hover: underline + `violet-ink`. Opens the email (`demux.openSource`).

### 7.10 Build flow (questions + progress)
One card takes the user from Build to a ready workspace. Demux asks only what the prompt leaves open, while it already works in the background, then shows the work. There are always three steps, in this order:

| # | Step (label) | Whose turn | Title (title-lg) |
|---|---|---|---|
| 1 | Your request | Demux, then the user if the prompt has gaps | "Understanding your request", then "A few questions" once there are questions |
| 2 | Reading your emails | Demux | Reading your emails |
| 3 | Building your workspace | Demux | Almost there |

There is no look step and no layout step: Demux never asks for colours, themes or a layout picked from a fixed list. Every question is written by the agent for this prompt.

Small and quiet: a short checklist, not an illustration. Steps 2 and 3 really run **at the same time** (the interface is designed while the emails are read), so both rows can be working at once.

**Card:** white, radius 24, padding 28/28/24, max-width 520, `shadow-float`. Top to bottom:
1. **Title row:** logo mark 28px with "breathe", then the step's title (table above) 20/600 ink, `reveal-text` on each change (focus moves to it), and on the right a quiet text button **Cancel** (13/500 `ink-3`, 44px hit target, `danger` on hover). It is there at every step, questions included.
2. **Prompt:** quoted, 14px `ink-3`, one line, truncated (full text in `title`), 6px under the title.
3. **Body** (20px under the prompt): the questions while it is the user's turn (step 1 below); otherwise **the checklist** and **the thinking line**.
4. **Footer row:** a note on the left (13px `ink-3`); while there are questions, the primary **Continue →** on the right (the card's only violet button).

**Checklist:** three rows, 36px tall, gap 2: a 16px status (empty circle `pending-line` waiting, spinner working, violet check done), the label 14/500 (`ink-3` waiting, ink otherwise), and on the right 13px `ink-3` tabular detail.
1. **Understanding your request:** detail "Your turn" while there are questions.
2. **Reading your emails:** "48 of 80" once the count is known.
3. **Designing your interface:** "Fixing a check", "Checking it with your data" when the designer says so; nothing while it simply works.
The list is the step's `role="progressbar"`: `aria-valuenow` = step, `aria-valuemax` = 3, `aria-valuetext="Step 2 of 3: Reading your emails"`.

**Thinking line:** under the list, 13px: a verb in -ing with an ellipsis, `ink-2`, changing every 2.8s from the current phase's list, its letters rippling in opacity (`ripple`; never gradient text, principle 5), then the latest real event in `ink-3` ("· Saved 3 expense records"). `aria-live="polite"` announces only the real events, never the verbs. The verbs are flavour; facts come only from the run's events.
- Your request: Reading your request · Searching your inbox · Sampling threads · Spotting patterns
- Reading: Untangling threads · Sorting · Matching replies · Cross-checking dates · Tallying amounts
- Designing (once reading is done): Sketching the layout · Choosing a palette · Setting the numbers · Polishing

When the workspace is ready, the page moves to it with `page`.

**Cancel** asks first, inline: the bottom of the card becomes a `danger-bg` strip (radius 12, padding 12/16): "Stop this build? The workspace is removed and your prompt goes back in the box." 14px `danger`, with quiet **Keep building** and a `danger` text button **Stop build** (spinner while it works). Stopping deletes the workspace (the worker stops its run within 2 s, so it stops spending) and opens Create with the prompt already in the prompt card, ready to reword. Escape or Keep building closes the strip.

**Step bodies**
- **1 · Your request.** While the agent searches the mailbox and looks for gaps: 22px spinner + "Looking at your emails" 15/500 `ink-2`, and no Continue. A precise prompt has no gaps: the step ticks off on its own and the card moves to step 2. Otherwise the agent asks **one question per gap** (1–2 for a fairly clear prompt, up to 5 for a vague one), all on one card: `<fieldset>`s, gap 24. Each: `<legend>` 16/600 ink (the agent's question, specific to this prompt and usually starting with what it found, e.g. "I found orders from Amazon, Zalando and Uber Eats. Should food deliveries count?" or "Do you want to follow each order until it arrives, or only see what is late?"), then radio rows: min-height 44px, radius 12, 1px `line`, padding 0 14, 15/500 `ink-2`, 18px radio. Selected: `violet-soft` background, `violet-line` border, `violet-ink` text. The agent's best guess is preselected and carries a "Recommended" tag (§7.7) on the right. The last row, "Other…", shows a text input (40px, radius 12, §7.4 rules) when chosen. Footer note: "We picked our best guess for each. Change what doesn't fit."
- **1 · Your request, Demux's turn.** Row 1 working, rows 2–3 waiting, the thinking line.
- **2 · Reading your emails.** Rows 2 and 3 working side by side. Footer note, from here on: "That's everything we need from you. You can close this page; your workspace will be ready here."
- **3 · Almost there.** Row 2 checked; row 3 still works (or the interface is being checked against the data).

**Behaviour**
- Steps only move forward, with the `step` motion (§9). The total is always 3: a skipped step fills like a done one.
- Answers are saved as soon as the user presses Continue.
- Questions left unanswered for 2 minutes: the build continues with the preselected answers, and the card says so under the title, 13px `ink-3`: "We went ahead with the recommended answers."
- The answers shape the workspace: what counts, what is tracked, how records are grouped and what the interface shows first.
- Opening the page mid-build (a reload, another tab, coming back later) resumes at the current step, with answered steps shown as done.
- Failure and "can't build" keep the existing copy (§11) inside the same card.
- `prefers-reduced-motion`: no `breathe`, `ripple` or `reveal-text`; the verbs change without the ripple.

### 7.11 Top bar (app)
Padding 18px top, sits on sky (no bar background). Used while a workspace is building or failed; a ready workspace has the floating bar instead (below). Left padding is `var(--dmx-gutter)`: 80px while the sidebar is closed (room for its open button, §7.13), 24px while it is open beside the page; the padding eases with the sidebar (360ms `ease-dmx-out`). Workspace page: workspace name (title-sm) + rename (ghost icon) or status chip on the left; sync status and More (⋯: Rename, Delete) on the right. No Undo and no Chat in the MVP. No sync button: workspaces sync on their own (every few minutes, and the page refreshes when it comes back into view). No workspace details are shown to users. No back button and no avatar: workspaces and the account live in the sidebar. The create and profile pages have no top bar.

**Floating bar (ready workspace).** A generated app has its own look (often dark), so Demux puts no frame around it: no sky, no top bar. Its controls float over the app's top-right corner instead, as small as they can be: 12px from the top and right, `glass`, radius full, `shadow-glass`. Idle, that is only More (⋯, 44px), mirroring the sidebar's open button in the other corner; its menu starts with the sync status (13/500, above a `line-soft` divider), then Rename, Open in new tab, Delete. While a run is active the bar grows into a pill (padding 4px) with the status chip before ⋯. Rename turns the pill into the name field (§7.4, 260px). Banners (reconnect, action errors, display error) float under the pill, centered, max 560px. Nothing else is drawn over the app.

### 7.13 App sidebar (navigation)
The only navigation in the signed-in app. Notion-like: from 768px it is a column beside the page and **pushes** it (the page shrinks while it is open and takes the full width when it closes); below 768px it floats over the page with a scrim. Open by default from 768px, closed below; the user's toggle then holds while they move between pages (not across reloads).
- **Panel:** white, radius `xl` (26px), `shadow-panel`, 12px from the top, left and bottom edges, width `min(300px, 100vw − 24px)`, padding 12px. The column is 312px (margin + panel) and animates its width to 0 when closed.
- **Close button:** on the **right** of the sidebar header, ghost icon (§7.1) on white: 44px circle, `panel-left-close` 20px `ink-3`, `surface-2` hover.
- **Open button:** shown only while the sidebar is closed: icon button on sky, `panel-left-open` 20px, fixed top 18px / left 24px. Both toggles carry `aria-expanded` + `aria-controls`, and focus moves to whichever one appears.
- **Below 768px:** scrim `rgb(12 26 46 / .18)` (no blur: the sidebar has its own view-transition name, which makes it a backdrop root); a click on it, Escape, or choosing a page closes the sidebar. From 768px choosing a page keeps it open.
- **On a ready workspace** the sidebar starts closed at every width, so the app has the whole window; the open button floats over the app's top-left corner. Once the user opens or closes it, their choice holds as everywhere else.
- **Click outside closes it** at every width: a press anywhere outside the panel (the page, the top bar, inside a workspace's app) closes an open sidebar; the open button brings it back.
- **Contents, top to bottom:**
  1. Header row (44px): lockup (28px mark, "Demux", opens the workspaces list: `/workspaces`, §8.0) on the left, close button on the right.
  2. **Create workspace** row (44px, radius full, `plus` in a 28px `violet-soft` circle, 15/500 ink). Hidden once both workspaces are used; the list then says "You're using both workspaces. Delete one to build another."
  3. **Workspaces** disclosure: header button 13/500 `ink-3` with a `chevron-down` that turns −90° when collapsed, "1 of 2" on the right (tabular). Rows: 44px, radius full, 7px dot (live green when ready, pulsing violet while building, danger when failed) + name 14/500 truncated, "Building" / "Failed" 12px on the right. Selected row: `violet-soft` bg, `violet-ink` text. Empty: "No workspaces yet" 13px `ink-3`.
  4. Footer, pinned to the bottom with a `line-soft` divider: the **account row**.
- **Account row:** like Claude's: 36px avatar (initial on `violet-soft` / `violet-ink`), full name 14/600 and login email 13 `ink-3` (both truncated), `chevrons-up-down` 16px. Opens a card above it (`pop` from the bottom): "Signed in as" + login email, the Gmail line ("Reading from [gmail]" / "Gmail not connected" / "Gmail needs reconnecting"), "1 of 2 workspaces", a **Profile** row (`user-round`, chevron that nudges) and, under it, a **Log out** row (`log-out`, spinner while signing out).
- Selection and focus inside the sidebar use violet, as everywhere else. No brand gradient besides the logo.

### 7.14 Admin pages (internal, `/admin`)
Demux staff only (admins: `ADMIN_EMAILS` or `users.is_admin`; everyone else gets the app's 404). Dense, plain and quiet: they are for reading numbers, not for showing off.
- **Shell:** sky + grain like every page, no app sidebar. Top bar (padding 18px 24px): lockup 28px + "Admin" 14/500 `ink-on-sky` on the left; a segmented control (§7.5, on sky) with **Overview · Users · Access · Demo inbox** in the middle; a secondary "Back to Demux" button on the right. Content column max 1240px, padding 0 24 48, groups separated by gap 16.
- **Surfaces:** white cards, radius `lg` (20px), `shadow-glass`, padding 20/22. Never glass for data. Card title 15/600 ink, an optional one-line note 13px `ink-3` under it.
- **Stat tiles:** a row of white tiles (min 160px, wrap), label 13/500 `ink-3` on top, value 28/500 −0.02em ink, tabular; an optional sub-line 13px `ink-3` ("3 failed of 41").
- **Tables:** inside a white card, 14px, rows 44px with `line-soft` dividers, header 13/500 `ink-3` (sortable headers are buttons with a 14px chevron; `aria-sort`). Numbers right-aligned, tabular. A row that opens a detail page is a link on its first cell.
- **Charts:** inside cards, height 220px. Thin bars (2px surface gap, 4px rounded ends), 2px lines, `line-soft` grid, 12px `ink-3` axis text, no axis lines. Hover tooltip on every chart: white, radius 12, 1px `line`, `shadow-glass`, 13px. A legend under every chart with two or more series; every chart has a "Show table" toggle (13/500 `ink-2`) for exact values. Series colours (the only place besides generated apps where non-brand hues appear; validated for colour-blind separation on white):

  | Slot | Token | Hex | Used for |
  |---|---|---|---|
  | 1 | `chart-1` | `#6A3DF0` | design · first model · tokens in · p50 |
  | 2 | `chart-2` | `#EB6834` | batch · second model · tokens out · p95 |
  | 3 | `chart-3` | `#1BAF7A` | app · third model |
  | 4 | `chart-4` | `#2A78D6` | edit · fourth model |
  | 5 | `chart-5` | `#D63A7C` | seed (demo inbox) · other models |

  Slots are assigned in this fixed order by the entity (a phase keeps its colour when others are hidden). Failure rate uses `danger`.
- **Range picker:** segmented control "7 days · 30 days · 90 days", top right of the page header.
- **Privacy:** admin pages show prompts and edit messages (typed by the user), counts, tokens and costs. Never email content, subjects, senders, record values, the guide or app HTML. A one-line reminder sits in the footer: "Shown: prompts, edit messages, counts and costs. Never email content."

### 7.12 Avatars (people in emails)
44px circle (40 on mobile), initials 14–15/600, soft background + dark text pairs: `#DCE9F9/#1F5FB8`, `#FCE3D6/#9A3B12`, `#E9E1FB/#5A33C8`, `#E4F5EA/#1D6B37`. Choose the pair from a hash of the sender's email so it stays stable.

---

## 8. Screens (MVP)

Desktop first (min 1280px). Mobile layout is out of MVP scope, but every page must still work at 390px: rows wrap, the side panel stacks under the app.

Every signed-in page (`/workspaces…`, `/profile`) lives inside one shell: the sky and the sidebar (§7.13). Pages change beside it; the sidebar never re-mounts.

0. **Login** (`/login`): sky + lockup top left. Centered white card (max 440, radius 30, `shadow-float`): mark 46px, title-lg "Sign in to Demux" / "Create your account", first name + last name side by side (sign-up only, both required; they become "Hello, [first name]"), email + password fields (labels 13/500 `ink-2`, inputs 48px, radius 12), full-width primary, a text link to switch. Sign-up only works for an email with access (a Stripe subscription, including its 14-day free trial, free access, or an admin); the subtitle says "Use the email you subscribed or were invited with." and a refused email gets the danger note with an inline violet link "Start a free trial at usedemux.com". `/login?mode=sign-up` opens on Create your account (the landing page links there after checkout). Then **Check your email**: 6 code boxes (56px tall, radius 12, one real `<input autocomplete="one-time-code">`), primary "Verify", "Resend code" (30 s cooldown) and "Use a different email". Trust line under the card.
0. **Workspaces** (`/workspaces`, where sign-in lands; the sidebar lockup opens it): with no workspace yet it opens **Create**. Otherwise a centered column (max 760, top padding like Create): title-lg "Your workspaces" (`reveal-text`) and "Open one to see it." 16 `ink-on-sky`, then one workspace card per row (§7.8), gap 10. Each card is a link: name 16/600 truncated, meta 13 `ink-2` with the sidebar's dot ("Synced 3 min ago · 14 invoices", "Building", "Failed"), the prompt on one line 14 `ink-3` (truncated, full text in `title`), and a chevron right that nudges on hover. The workspace opened last in this browser carries a "Last opened" tag (§7.7) after its name. While a slot is free, an empty slot (§7.8) under the cards links to Create: `plus` 16px + "Create workspace". This page loads only the list (names, statuses, counts): a workspace's app and data load once it is opened, and pointing at or focusing a card starts loading the app frame so it opens faster. Opening `/workspaces` never jumps into a workspace on its own.
1. **Create, connect** (`/workspaces/new` while no Gmail is connected or it needs a reconnect): centered white card (max 520, radius 30, `shadow-float`): breathing mark 56px, title-lg "Connect your Gmail", one sentence, primary "Connect with Google →", trust line. Google's errors show in the card.
2. **Create, prompt** (`/workspaces/new` once Gmail is connected): centered, top third: title-xl "Hello, [first name]" (the first name from sign-up or the profile page; just "Hello" for older accounts without one), then "What do you want to track?" 22/500 `ink-on-sky`, the prompt card (max 760; after a cancelled build it opens with that build's prompt in it), the read-only line with a lock icon. With both workspaces used, the prompt is disabled and a limit notice replaces the read-only line: a white card (max 760, radius 20, `shadow-panel`, padding 16/20) with "Workspace limit reached" 15/600 ink and "You can have 2 workspaces. Delete one to create a new one." 14 `ink-2`. Build opens the new workspace in the same area.
3. **Workspace, building** (`/workspaces/[id]`, status `building`): sky + top bar (name, Building chip). Centered build flow card (§7.10). Nothing else.
4. **Result** (`/workspaces/[id]`, status `ready`): the app **full bleed**: the sandboxed iframe fills the page beside the sidebar, edge to edge, no padding, no radius, no sky around it, so the app's own colours never sit inside Demux's blue. Demux's controls float over it: the sidebar's open button (top left, §7.13) and the floating bar (top right, §7.11). The chat side panel is removed for the MVP (`ChatPanel` and `SidePanel` are kept for when it returns).
   - Display error banner (floating under the bar, top): bg `#FDECEA`, text `#A8321F`, "This workspace hit a display error", violet "Fix it" button.
   - Reconnect banner (floating under the bar): glass card, ink text, primary button "Reconnect Gmail".
4b. **App alone** (`/workspaces/[id]/app`, from More → Open in new tab): only the app, full window, outside the app shell: no sidebar, no bar, no controls. The tab title is the workspace name. It refreshes like the workspace page. While the workspace is not ready, or when it can't be loaded, a centered white card (max 440, radius 30, `shadow-float`) on sky says so, with a secondary "Open in Demux" link. A display error shows the danger banner floating at the top, with an "Open in Demux" link (fixing happens there).
5. **Profile** (`/profile`, from the account card): centered column (max 640), title-lg "Profile" + "Your name and the Gmail Demux reads." `ink-on-sky`, then two white cards (radius 26, `shadow-panel`, padding 24/28): **Your name** (first + last name fields side by side, both required, primary "Save" (small) on the right, "✓ Saved" `violet-ink` beside it after saving) and **Account** (sign-in email, read-only; "Gmail Demux reads" with a quiet button "Use another account" / "Connect Gmail" / "Reconnect Gmail" that goes through Google and comes back here, and, while a Gmail is connected, a quiet "Disconnect" beside it. Disconnect asks first, inline in the same row: "Disconnect [gmail]? Your workspaces stay but stop updating." with quiet "Cancel" and a `danger` text "Disconnect" button; then the row reads "Not connected"; the read-only trust line).

5b. **No access** (any signed-in page, when the user has no subscription, trial or free access any more): the shell shows this instead of the sidebar and page. Sky + lockup top left, like Login. Centered white card (max 480, radius 30, `shadow-float`): mark 46px, title-lg "Your Demux access has ended", one sentence that the workspaces are kept, "Signed in as [email]" 13px `ink-3`, the screen's one primary **Subscribe →** (to the landing page's pricing card), then a row with quiet text buttons "I've subscribed, check again" (spinner while checking; "Still no active subscription for [email]." in a `violet-soft` note if nothing changed) and "Log out". The 15 s poll unlocks the app on its own once a subscription arrives.
6. **Admin** (`/admin`, `/admin/users`, `/admin/users/[id]`, `/admin/workspaces/[id]`, `/admin/access`, `/admin/demo`; §7.14). Overview: title-lg "Usage" + range picker, stat tiles (active users, workspaces, builds / syncs / edits, tokens in, tokens out, cost), four chart cards (daily cost by phase with a "By phase / By model" toggle, tokens in vs out, cost per active user p50 / p95, run failure rate). Users: one table, sorted by cost (30 days), with an Access pill per user (Admin · Subscribed · Free access · Trial · No access). Access: a "Give free access" card (email, optional note, an "Ends" select: Never / 1 month / 3 months / 1 year, and the page's primary **Give access**), the free-access table (email, note, status pill, account yes/no, ends, granted by, a `danger` text "Revoke" that asks inline first), and a Stripe customers table (email, status pill (trialing, active, past due, canceled), trial end, access, account, updated) with a quiet "Sync from Stripe" button. A danger note at the top while STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET is missing. User: header card (email, signed up, last active, Gmail state) + stat tiles + a mail-volume chart + one card per workspace (prompt, counts, runs table, edit messages). Workspace: cost and emails-per-day charts + runs table. Demo inbox: one white card with a textarea "Who is the inbox owner, and what threads do they get?", a thread-count select and the page's primary **Write threads** button; a list of past requests with status; a quiet "Move demo threads to Trash" button.

---

## 9. Motion

The app should feel alive but calm, like a well-made native app: things arrive in a
short sequence, surfaces respond to the pointer, and the sky moves almost imperceptibly.
Two curves only: `ease-dmx` `cubic-bezier(.2,.8,.2,1)` for state changes (hover, focus,
tabs) and `ease-dmx-out` `cubic-bezier(.16,1,.3,1)` (a long, soft settle) for anything
entering the screen.

| Name | Spec | Use |
|---|---|---|
| `spin` | rotate 360°, 0.9s linear infinite | Active step spinner, button loading |
| `pulse` | opacity 1 → .35 → 1, 1.6s ease-in-out | Building dot |
| `breathe` | scale 1 → 1.045 → 1, 2.4s ease-in-out | Logo on the build card |
| `flow` | background-position 0 → 200px, 1.8s linear | A gradient that moves while Demux works (`background-size: 200px 100%`; the 200px tile runs violet → magenta → coral → magenta → violet so it loops without a seam). No current use |
| `ripple` | each letter: opacity 1 → .45 → 1, 1.6s ease-in-out infinite, 40ms stagger | The build card's thinking line (§7.10) |
| `blink` | opacity steps, 1.1s | Text caret (marketing demos only) |
| `reveal` | fade + 16px rise, 700ms `ease-dmx-out`, stagger 80ms | Blocks entering a screen in reading order: title → card → helper line → list (`<Reveal index>`) |
| `reveal-text` | each word: fade + 0.4em rise + 8px blur → sharp, 800ms `ease-dmx-out`, stagger 45ms | Page titles only (title-xl / title-lg), at most one per screen (`<RevealText>`) |
| `pop` | fade + scale .96 + 4px from the anchor, 200ms `ease-dmx-out`, origin at the trigger | Menus and popovers |
| `drawer` | from 768px: the sidebar column's width and the panel's slide move together, 360ms `ease-dmx-out`, both ways, and the page reflows with them · below 768px: panel slides in 420ms `ease-dmx-out` (out 260ms `ease-dmx`), scrim fades 300ms · rows follow an opening panel with fade + 8px from the left, 30ms stagger; nothing animates on page load | App sidebar (§7.13). The sidebar keeps its own view-transition name so page changes never paint over it |
| UI transitions | 150–200ms `ease-dmx` | Hover, focus, tab switch |
| Hover lift | interactive cards rise 2px and their shadow deepens one step (`shadow-glass` → `shadow-panel`), 250ms; pressed: scale .99 | Workspace cards, example chips (1px) |
| Arrow nudge | trailing arrow moves 3px in its direction on hover of its button, 200ms | Build →, Continue →, Connect Gmail → |
| `page` | old: fade + 4px up + 2px blur, 160ms · new: fade + 12px rise + 4px blur → sharp, 420ms `ease-dmx-out` after 60ms | Route changes (React `<ViewTransition>`), the sky stays still |
| `step` | old: fade + 12px left, 150ms · new: fade + 16px from right, 380ms `ease-dmx-out` | Steps inside one page (sign in → code, connect → prompt, the build flow steps §7.10) |
| Record update | 600ms fade of the violet highlight | §7.8 |

Rules:
- Entrances play once, when the screen appears. Polling and live updates never replay them.
- Never animate more than ~6 reveal steps on one screen; the whole sequence settles within 1s.
- Hover motion is for things you can click. Static content never moves on hover.
- Nothing large loops forever. Infinite animations stay small (a spinner, a 28px mark, a status dot): an endless full-screen or backdrop animation repaints the whole page every frame and makes everything else stutter.
- Respect `prefers-reduced-motion: reduce`: every loop, entrance and lift is off and content shows in its final state. No bouncing, no confetti, no parallax, no scroll-jacking.

---

## 10. Implementation (Next.js App Router + Tailwind v4)

### 10.1 Font — `src/app/layout.tsx`
```tsx
import { Instrument_Sans } from "next/font/google";
const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-instrument-sans",
  display: "swap",
});
// <html lang="en" className={instrumentSans.variable}>
```

### 10.2 Tokens — `src/app/globals.css`
```css
@import "tailwindcss";

@theme {
  /* Remove Tailwind's default palette: only brand colors exist. */
  --color-*: initial;
  --color-white: #FFFFFF;
  --color-black: #000000;

  /* Primary — sky (backgrounds only) */
  --color-sky-deep: #3F92F0;
  --color-sky-500: #5EA7F4;
  --color-sky-300: #8DBDEE;
  --color-sky-200: #A9CBF0;
  --color-haze: #CAD7E8;
  --color-mist: #DFE2E7;

  /* Secondary — logo */
  --color-violet: #6A3DF0;
  --color-violet-hover: #5A2FDC;
  --color-violet-ink: #4B24C9;
  --color-violet-soft: #EEE9FE;
  --color-violet-line: #C9BCFB;
  --color-violet-tint: #FBFAFF;
  --color-magenta: #D63A7C;
  --color-magenta-soft: #FCE3EC;
  --color-coral: #EE5A44;

  /* Ink & surfaces */
  --color-ink: #0C1A2E;
  --color-ink-2: #33445C;
  --color-ink-3: #5B6B80;
  --color-ink-on-sky: #172741;
  --color-line: #E6EBF2;
  --color-line-soft: #EDF1F6;
  --color-surface: #FFFFFF;
  --color-surface-2: #F4F7FB;
  --color-surface-3: #F5F7FB;
  --color-tag: #F1F4F8;

  /* Status */
  --color-success-bg: #E4F5EA;  --color-success: #1D6B37;
  --color-danger-bg: #FDECEA;   --color-danger: #A8321F;
  --color-warning-bg: #FFF1E2;  --color-warning: #8F4405;
  --color-info-bg: #E6F0FD;     --color-info: #1F5FB8;
  --color-neutral-bg: #EEF2F7;  --color-neutral: #33445C;
  --color-live: #2FB36B;

  /* Type */
  --font-sans: var(--font-instrument-sans), -apple-system, "Helvetica Neue", Arial, sans-serif;

  /* Radius */
  --radius-tag: 6px;
  --radius-sm: 12px;
  --radius-md: 16px;
  --radius-lg: 20px;
  --radius-xl: 26px;
  --radius-2xl: 30px;

  /* Shadows */
  --shadow-float: 0 50px 90px -40px rgb(22 62 128 / .55), 0 2px 8px rgb(22 62 128 / .06);
  --shadow-panel: 0 40px 80px -40px rgb(22 62 128 / .50), 0 2px 6px rgb(22 62 128 / .05);
  --shadow-glass: 0 20px 40px -28px rgb(22 62 128 / .50);
  --shadow-pill: 0 6px 14px -8px rgb(22 62 128 / .50);
  --shadow-input: 0 10px 24px -16px rgb(22 62 128 / .45);

  /* Motion */
  --ease-dmx: cubic-bezier(.2,.8,.2,1);
  --ease-dmx-out: cubic-bezier(.16,1,.3,1);
  --animate-dmx-pop: dmx-pop .2s var(--ease-dmx-out) both;
  --animate-dmx-spin: dmx-spin .9s linear infinite;
  --animate-dmx-pulse: dmx-pulse 1.6s ease-in-out infinite;
  --animate-dmx-breathe: dmx-breathe 2.4s ease-in-out infinite;
  --animate-dmx-flow: dmx-flow 1.8s linear infinite;
  @keyframes dmx-spin { to { transform: rotate(360deg); } }
  @keyframes dmx-pulse { 50% { opacity: .35; } }
  @keyframes dmx-breathe { 50% { transform: scale(1.045); } }
  @keyframes dmx-flow { from { background-position: 0 0; } to { background-position: 200px 0; } }
  /* + dmx-reveal, dmx-reveal-word, dmx-pop (§9); see globals.css */
}

@layer base {
  html { color: var(--color-ink); -webkit-font-smoothing: antialiased; }
  body { font-family: var(--font-sans); }
  ::selection { background: var(--color-violet-soft); color: var(--color-violet-ink); }
  :focus-visible { outline: none; box-shadow: 0 0 0 3px rgb(106 61 240 / .22); }
  button, input, textarea { font: inherit; }
}

@utility bg-sky {
  background-color: #8DBDEE;
  background-image:
    radial-gradient(70% 70% at 6% 0%,   rgb(86 162 244 / .95),  rgb(86 162 244 / 0) 70%),
    radial-gradient(55% 60% at 100% 4%, rgb(112 178 247 / .90), rgb(112 178 247 / 0) 70%),
    radial-gradient(50% 50% at 86% 78%, rgb(208 220 234 / .95), rgb(208 220 234 / 0) 70%),
    radial-gradient(45% 50% at 4% 100%, rgb(226 230 236 / .95), rgb(226 230 236 / 0) 70%),
    radial-gradient(40% 45% at 100% 100%, rgb(72 152 242 / .85), rgb(72 152 242 / 0) 70%);
}
@utility bg-brand-gradient { background-image: linear-gradient(90deg, #6A3DF0 0%, #D63A7C 60%, #EE5A44 100%); }
@utility glass { background: rgb(255 255 255 / .72); border: 1px solid rgb(255 255 255 / .85); backdrop-filter: blur(20px); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```
Put the grain from §4.2 on the page shell component (the element that has `bg-sky`, with `position: relative`).

### 10.3 Generated apps (sandboxed iframe)
**Studio apps (v3, every new app) do not follow this design system.** The interface designer (the UI model, `UI_MODEL`, GLM-5.2) designs each workspace's experience and look from scratch: its own palette, type pairing, layout, light or dark, charts and motion, chosen for that workspace's subject. The app is shown full bleed (§8.4): Demux draws no frame around it, only its sidebar beside it and two floating controls over its top corners, which the designer's prompt tells it to keep clear. The plan is `docs/UI_GENERATION_PLAN.md` §11.

- **What the shell gives a studio app:** the studio runtime (React 19, Recharts, an `Icon` set from lucide, the data helpers), Tailwind v4 compiled in the iframe, and embedded fonts: Inter (`font-sans`), Space Grotesk (`font-display`), Fraunces (`font-serif`), Instrument Serif (`font-editorial`), JetBrains Mono (`font-mono`). No Demux tokens, palettes or base classes. The reference the designer reads is `app-kit/src/studio.md`.
- **What stays fixed:** the sandbox and CSP (no network, no navigation, inline scripts only), the app check (it must render, show the data, survive empty data, render the same twice), and the bridge (`openEmail` / `demux.openSource`, `demux.openLink`).
- **Quality bar the designer is held to** (its prompt, `INTERFACE` in `backend/app/agent/prompts.py`): high-end and specific to the workspace, never a generic white dashboard; the answer to the request first and at a glance; a deliberate palette with consistent meaning and AA contrast; tabular numbers; every state designed (empty, one, many, missing fields); works from 390px wide without sideways scrolling.
- **Changing the look later:** any request about what the workspace shows or how it looks, colours included, goes from the chat agent to the designer (`change_interface`).

Everything below applies to **older apps only**: kit apps (v2) and plain HTML apps (v1), built before the designer. They keep working, styled by the shell; the first interface change to one of them has the designer rewrite it as a studio app.

**Shell (v1, v2).** The iframe's CSP allows `font-src data:` only, so Google Fonts cannot load inside it. The shell inlines Instrument Sans latin 400/500/600 as base64 `@font-face` (system stack as fallback), the tokens below as CSS variables, the palettes, and the component kit (v2 apps) or the base classes (v1 apps). The iframe and the headless app check use the same shell.

**Fixed tokens**, identical in every palette:
```css
:root{
  --dmx-font: "Instrument Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  --dmx-ink:#0C1A2E; --dmx-ink-2:#33445C; --dmx-ink-3:#5B6B80;
  --dmx-surface:#FFFFFF; --dmx-surface-2:#F4F7FB; --dmx-line:#E6EBF2; --dmx-line-soft:#EDF1F6; --dmx-tag:#F1F4F8;
  --dmx-success-bg:#E4F5EA; --dmx-success:#1D6B37; --dmx-danger-bg:#FDECEA; --dmx-danger:#A8321F;
  --dmx-warning-bg:#FFF1E2; --dmx-warning:#8F4405; --dmx-info-bg:#E6F0FD; --dmx-info:#1F5FB8;
  --dmx-neutral-bg:#EEF2F7; --dmx-neutral:#33445C;
  --dmx-cat-blue:#5EA7F4; --dmx-cat-lavender:#9A8BF7; --dmx-cat-pink:#E0679A;
  --dmx-cat-green:#2FB36B; --dmx-cat-amber:#F5A524; --dmx-cat-purple:#9A7BF7;
  --dmx-series-other:#AEB8C6;
  --dmx-r-tag:6px; --dmx-r-card:12px; --dmx-r-col:16px; --dmx-r-pill:999px;
}
```

**Palettes.** A palette sets the accent family and the chart series order, nothing else. The shell sets it on the root (`<html data-palette="teal">`, or live through the bridge message `demux:palette`); missing or unknown means `violet`. It is stored per workspace (`workspaces.palette`, `violet` by default). The build no longer asks for it (§7.10); it does not change afterwards, and Undo does not touch it.

| Palette | `--dmx-accent` | `-accent-hover` | `-accent-ink` | `-accent-soft` | `-accent-line` | `-accent-tint` |
|---|---|---|---|---|---|---|
| **Violet** (default) | `#6A3DF0` | `#5A2FDC` | `#4B24C9` | `#EEE9FE` | `#C9BCFB` | `#FBFAFF` |
| Ocean | `#0E67B0` | `#0B5794` | `#0A4A80` | `#E1F0FB` | `#ADD3F0` | `#F7FBFE` |
| Teal | `#0F766E` | `#0B615A` | `#0A5650` | `#DDF3EF` | `#A6DCD3` | `#F6FCFB` |
| Rose | `#C02C6C` | `#A6235C` | `#921C50` | `#FCE6EF` | `#F2B8CF` | `#FFF9FB` |
| Graphite | `#2E3D54` | `#1E2A3D` | `#1E2A3D` | `#E6EAF0` | `#C3CCD8` | `#F9FAFC` |

Derived from the accent in every palette: `--dmx-accent-ring` (the accent at 22% opacity, the focus ring) and `--dmx-accent-glow` (8%, the just-updated halo). Each palette also sets `--dmx-series-1` … `--dmx-series-5`, the order for chart series and category dots. Series 1 is always the accent; series 2–5 are `--dmx-cat-*` colours, leaving out the one closest to the accent:

| Palette | Series 2 · 3 · 4 · 5 |
|---|---|
| Violet | blue · pink · green · amber |
| Ocean | lavender · pink · green · amber |
| Teal | amber · lavender · pink · blue |
| Rose | blue · green · amber · lavender |
| Graphite | blue · amber · green · pink |

Contrast (WCAG 2.x, checked):

| Palette | white on accent (= accent on white) | white on accent-hover | accent-ink on accent-soft | accent on accent-tint |
|---|---|---|---|---|
| Violet | 5.9 | 7.3 | 7.4 | 5.7 |
| Ocean | 5.9 | 7.5 | 7.8 | 5.6 |
| Teal | 5.5 | 7.3 | 7.4 | 5.3 |
| Rose | 5.5 | 7.0 | 7.1 | 5.3 |
| Graphite | 11.0 | 14.4 | 12.0 | 10.5 |

Series colours are 2.0–3.2:1 on white, so they never carry meaning alone: always a legend, a direct label, or a text label next to the dot.

Why these five: their hues stay away from the status colours (§3.4). There is no green, orange or red palette, because it would read as success, warning or danger. Ocean (207°) sits close to info (215°); its Updated tag keeps the dot and the "Updated" text, so it still reads differently from an info pill. Graphite is the quietest: its highlight is grey, close to the neutral pill.

**Rules**
- Palettes exist **only inside v1 and v2 apps**. Demux's own UI (sidebar, top bar, cards, build flow) stays violet whatever the workspace's palette.
- A palette changes the accent family and the series order only. Neutrals, status pairs, type, radii and spacing never change.
- **No raw colours in v1 and v2 code:** no hex, `rgb()`, `hsl()` or named colours, only `var(--dmx-*)`. The app check rejects them (studio apps are exempt).
- No sky gradient and no brand gradient inside generated apps. The accent marks the selected or updated state, the main control, and series 1 of charts and category dots, nothing else. Status colours only for status.
- Charts: at most 5 series, in `--dmx-series-1…5` order; anything beyond is grouped into "Other" (`--dmx-series-other`). Flat fills: no gradients, 3D or shadows. Tabular numbers on axes and labels.
- The palette is not chosen by the user: there is no palette step in the build and no switcher in the workspace. A chat request for other colours has the designer rewrite the app as a studio app.

**Component kit (v2 apps).** Kit apps compose the kit: shadcn-based blocks (`Board`, `DataTable`, `Dashboard`, `StatCard`, `Chart`, `Timeline`, `Calendar`, `Gallery`, `ListDetail`, `RecordSheet`, `ViewTabs`, `FilterBar`, `EmptyState`) and primitives, restyled to this file rather than shadcn's defaults:
- Buttons: §7.1 pill shapes, in the palette's accent; one primary per app.
- Records: §7.8 record card, board column and just-updated highlight (in the palette's accent); §7.7 tags and status pills. A click opens the record in a side sheet (all fields, "Open email"); cards also carry a 28px mail icon button (`ink-3`, accent-soft on hover, label "Open email").
- Tables: header 13/500 `ink-3`, cells padded 10/12 with `line-soft` dividers, row hover `surface-2`, tabular numbers.
- Tabs: §7.5 segmented control with the `rgba(12,26,46,.06)` track.
- Type: §5 styles, weights 400/500/600 only, large numbers at 500. Icons: §10.4.
- The agent writes no CSS colours and no Tailwind classes: it passes props and lays blocks out with the kit's `Stack`, `Row`, `Grid` and `Section`.

**Base classes (v1 apps).** Apps built before the kit keep the base classes in `shell.py` (`.table`, `.card`, `.board` + `.column`, `.badge`, `.btn`, …). They style through the same variables, so palettes apply to them too.

### 10.4 Icons
Inline stroke SVG or `lucide-react`. Stroke 2px (2.2–2.4 on filled buttons), round caps and joins, sizes 14/16/18/20, color `currentColor`. Icons in use: `panel-left-open`, `panel-left-close`, `user-round`, `plus`, `chevron-down`, `chevrons-up-down`, `log-out`, `chevron-left`, `chevron-right`, `pencil`, `refresh-cw`, `undo-2`, `more-horizontal`, `arrow-right`, `arrow-up`, `check`, `lock`, `mail`. No filled or duotone icons, no emoji, no sparkles/wand/stars icons.

---

## 11. Voice and copy

- **Tone:** plain, short, concrete. Say what happened, with a real noun and a number. Sentence case. No exclamation marks.
- **Never write:** "AI-powered", "magic", "supercharge", "seamless", "unlock", "revolutionize", "✨", "Oops!".
- **Product vocabulary (fixed):** *workspace* (never "view" or "dashboard"), *prompt*, *build* (first run), *sync* (later runs), *record*, *field*, *message* (one email), *thread* (a conversation), *layout* (a board, table, timeline… inside a workspace; never "view" or "widget"), *look* (the workspace's palette, named by its palette name). "Live apps" is marketing-only.

| Context | Copy |
|---|---|
| Sign in | Sign in to Demux · Create your account · Check your email · We sent a 6-digit code to [email]. It expires in 10 minutes. |
| Sign-up access | Use the email you subscribed or were invited with. It doesn't have to be the Gmail you'll connect. · There's no Demux subscription for this email. Use the email you subscribed with, or subscribe first. · Start a free trial at usedemux.com |
| No access | Your Demux access has ended · Subscribe to keep using Demux. Your workspaces are saved and stop updating until then. · Signed in as [email] · Subscribe · I've subscribed, check again · Still no active subscription for [email]. · Log out |
| Admin access | Access · Give free access · For beta users and friends. They create their account with this email. · Give access · Free access · Revoke · Revoke access for [email]? · Stripe customers · Sync from Stripe |
| Connect | Connect your Gmail · Connect with Google · Reading from [gmail] · Use another account |
| Sidebar | Create workspace · Workspaces · No workspaces yet · Signed in as · Profile · Log out · Open sidebar / Close sidebar (labels) |
| Profile | Profile · Your name and the Gmail Demux reads. · Your name · Demux greets you by your first name. · Save · Saved · Sign-in email · Gmail Demux reads · Disconnect · Disconnect [gmail]? Your workspaces stay but stop updating. · Cancel |
| Prompt page title | Hello, [first name] · What do you want to track? |
| Prompt placeholder | Describe what you want to keep track of… |
| Primary action | Build |
| Trust line | Read-only. Demux never sends or changes an email. |
| Workspace list | Workspaces · 1 of 2 · Your workspaces · Open one to see it. · Last opened · Create workspace |
| Limit reached | Workspace limit reached · You can have 2 workspaces. Delete one to create a new one. (sidebar: You're using both workspaces. Delete one to build another.) |
| Build steps | Your request · Reading your emails · Building your workspace |
| Step counter | Step 1 of 3 · Your request |
| Step 1 | Understanding your request · Looking at your emails · A few questions · Recommended · Other… · We picked our best guess for each. Change what doesn't fit. · Continue |
| Step 2 | Reading your emails · Collecting matching emails · 48 of 120 threads read · 14 shipments found so far |
| Step 3 | Almost there · Building your workspace |
| Slow load | This is taking longer than usual. · Reload |
| Your part done | That's everything we need from you. You can close this page; your workspace will be ready here. |
| No answer in time | We went ahead with the recommended answers. |
| Build failed | We couldn't build this workspace. [reason] · Try again |
| Sync status | Synced 3 min ago · Syncing… |
| Record updated | Updated 2 min ago |
| Live label | Live from your inbox |
| Display error | This workspace hit a display error · Fix it |
| Reconnect | Gmail disconnected. Reconnect to keep this workspace updated. · Reconnect Gmail |

---

## 12. Do / Don't

| Do | Don't |
|---|---|
| One focal element and one violet button per screen | Two primary buttons, or a violet button next to a dark one |
| Ink text on sky; white cards for anything dense | White text on the sky, or a table directly on the gradient |
| Violet for the thing the user can act on or just changed | Violet headings, decorative borders or shapes |
| Brand gradient on the logo and the build progress only | Gradient buttons, gradient text, gradient borders, glowing blobs |
| Soft-bg + dark-text status pills | Saturated solid pills with white text |
| Tinted blue shadows, large and soft | Black, hard or multiple stacked shadows |
| Generous whitespace, left-aligned dense content | Bento grids, feature-icon rows, filler sections |
| Real names, amounts and dates in examples | Lorem ipsum, "John Doe", invented % stats |
| Studio apps with a look designed for their workspace; v1/v2 apps coloured only through `--dmx-*` and one of the five palettes | A generic white admin dashboard as a studio app, raw hex/rgb in v1/v2 code, or a workspace's colours leaking into Demux's own UI |
| Build steps that ask one thing each, with the recommended answer preselected | Extra steps added mid-build, or a question without a default |