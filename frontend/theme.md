# Demux — Design System

> Context file for Claude Code. Read this before building or changing any UI in Demux.
> Source of truth for colors, type, components and copy. If code and this file disagree, this file wins. Change this file first, then the code.
> Visual reference: "Demux — Product Design" canvas (Prompt → Workspace → Result, plus a Colors & type sheet).

---

## 1. Principles (apply to every screen)

1. **One idea per screen.** Each screen has one focal element and one primary action. If a screen needs two primary buttons, it needs two screens.
2. **Sky behind, white in front.** The sky gradient is only a backdrop. Content always sits on white (or translucent white) surfaces.
3. **The logo colors mean "Demux is acting".** Violet, magenta and coral mark actions, focus, selection, live updates and build progress. They are never decoration.
4. **The full logo gradient appears at most once per screen.** Today that is only the logo and the build progress bar.
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

**Category dots** (columns, clients), 6–7px circles: `#5EA7F4` blue · `#9A8BF7` lavender · `#E0679A` pink · `#2FB36B` green · `#F5A524` amber · `#9A7BF7` purple. Dots are always paired with a text label: never color alone.

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

The sky is painted on a fixed layer behind the grain (`.dmx-sky` in the root layout) that slowly `drift`s (§9). The `body` keeps the plain `bg-sky` as its fallback.

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
| **Secondary on sky** (Sync now, Undo) | height 44px, px 16, radius full, `glass-strong` bg, ink 14px/500, leading icon 16px | `inline-flex items-center gap-2 h-11 px-4 rounded-full bg-white/60 text-ink text-sm font-medium hover:bg-white/90` |
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
- Footer row: example chips on the left, primary **Build →** on the right.
- Focus: no ring and no movement on the card; the violet caret is the focus cue.

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
- **Workspace card (list):** glass, radius 20, padding 16/18, `shadow-glass`. Title 16/600, meta 13 `ink-2` with live dot ("Synced 3 min ago · 14 invoices"), chevron right.
- **Empty slot:** min-h 72, radius 20, 1.5px dashed `rgba(12,26,46,.22)`, centered 14px `ink-on-sky` ("One more slot free").
- **Record card (board):** white, radius 12, padding 12/14, 1px `line`. Title 15/600 · client row 13 `ink-3` with 6px dot · tag.
- **Just-updated record:** bg `violet-tint`, border `violet-line`, `box-shadow: 0 0 0 3px rgba(106,61,240,.08)`, plus the Updated tag. The highlight stays until the user has seen it (page focus + 10s), then fades over 600ms.
- **Board column:** bg `surface-2`, radius 16, padding 12, gap 8. Header 13/500 `ink-2` + dot + count in `ink-3`.

### 7.9 Activity item (side panel)
Vertical list with dividers `line-on-glass`, padding 14px 0:
1. Time, 12px `ink-2` (newest item gets a 6px violet dot)
2. Record title, 15/600
3. Change: `from` pill (neutral) → arrow 14px `ink-3` → `to` pill (status color), or one sentence 13px `ink-2`
4. Source link: mail icon 14px + "Sender · “subject or quote”" 13px `ink-2`. Hover: underline + `violet-ink`. Opens the email (`demux.openSource`).

### 7.10 Build progress
- Card: white, radius 30, padding 36/36/24, max-width 620, `shadow-float`.
- Logo mark 56px with "breathe" animation, title-lg "Building your workspace", the prompt quoted in `ink-2`.
- Steps (`<ol>`), each row 16px with a divider:
  - **Done:** 28px circle `violet-soft` + violet check, label 16/500, right "Done" 13 `ink-3`.
  - **Active:** 22px spinner (2.5px `magenta-soft` track, `magenta` arc), label 16/600, right "Batch 3 of 12" 13 `ink-2`. Below it: 6px progress bar (track `#EEF1F6`, fill = brand gradient, `role="progressbar"`) and a live line 14px `ink-2` ("Found 9 requests from 4 clients so far").
  - **Pending:** 24px circle, 2px `#E1E6EE` border, label 16/500 `ink-3`.
- Footer 13px `ink-3`: "You can close this page. Demux keeps building, and your workspace will be ready here."
- Phases (fixed copy): Understanding your request → Reading your emails → Building the interface.

### 7.11 Top bar (app)
Padding 18px top, sits on sky (no bar background). Left padding is `var(--dmx-gutter)`: 80px while the sidebar is closed (room for its open button, §7.13), 24px while it is open beside the page; the padding eases with the sidebar (360ms `ease-dmx-out`). Workspace page: workspace name (title-sm) + rename (ghost icon) or status chip on the left; sync status, Sync now, Undo, Activity, More (⋯) on the right. No back button and no avatar: workspaces and the account live in the sidebar. The create and profile pages have no top bar.

### 7.13 App sidebar (navigation)
The only navigation in the signed-in app. Notion-like: from 768px it is a column beside the page and **pushes** it (the page shrinks while it is open and takes the full width when it closes); below 768px it floats over the page with a scrim. Open by default from 768px, closed below; the user's toggle then holds while they move between pages (not across reloads).
- **Panel:** white, radius `xl` (26px), `shadow-panel`, 12px from the top, left and bottom edges, width `min(300px, 100vw − 24px)`, padding 12px. The column is 312px (margin + panel) and animates its width to 0 when closed.
- **Close button:** on the **right** of the sidebar header, ghost icon (§7.1) on white: 44px circle, `panel-left-close` 20px `ink-3`, `surface-2` hover.
- **Open button:** shown only while the sidebar is closed: icon button on sky, `panel-left-open` 20px, fixed top 18px / left 24px. Both toggles carry `aria-expanded` + `aria-controls`, and focus moves to whichever one appears.
- **Below 768px:** scrim `rgb(12 26 46 / .18)` (no blur: the sidebar has its own view-transition name, which makes it a backdrop root); a click on it, Escape, or choosing a page closes the sidebar. From 768px choosing a page keeps it open.
- **Contents, top to bottom:**
  1. Header row (44px): lockup (28px mark, "Demux", links home) on the left, close button on the right.
  2. **Create workspace** row (44px, radius full, `plus` in a 28px `violet-soft` circle, 15/500 ink). Hidden once both workspaces are used; the list then says "You're using both workspaces. Delete one to build another."
  3. **Workspaces** disclosure: header button 13/500 `ink-3` with a `chevron-down` that turns −90° when collapsed, "1 of 2" on the right (tabular). Rows: 44px, radius full, 7px dot (live green when ready, pulsing violet while building, danger when failed) + name 14/500 truncated, "Building" / "Failed" 12px on the right. Selected row: `violet-soft` bg, `violet-ink` text. Empty: "No workspaces yet" 13px `ink-3`.
  4. Footer, pinned to the bottom with a `line-soft` divider: **account row** and **Log out** row.
- **Account row:** like Claude's: 36px avatar (initial on `violet-soft` / `violet-ink`), full name 14/600 and login email 13 `ink-3` (both truncated), `chevrons-up-down` 16px. Opens a card above it (`pop` from the bottom): "Signed in as" + login email, the Gmail line ("Reading from [gmail]" / "Gmail not connected" / "Gmail needs reconnecting"), "1 of 2 workspaces", and a **Profile** row (`user-round`, chevron that nudges).
- Selection and focus inside the sidebar use violet, as everywhere else. No brand gradient besides the logo.

### 7.12 Avatars (people in emails)
44px circle (40 on mobile), initials 14–15/600, soft background + dark text pairs: `#DCE9F9/#1F5FB8`, `#FCE3D6/#9A3B12`, `#E9E1FB/#5A33C8`, `#E4F5EA/#1D6B37`. Choose the pair from a hash of the sender's email so it stays stable.

---

## 8. Screens (MVP)

Desktop first (min 1280px). Mobile layout is out of MVP scope, but every page must still work at 390px: rows wrap, the side panel stacks under the app.

Every signed-in page (`/workspaces…`, `/profile`) lives inside one shell: the sky and the sidebar (§7.13). Pages change beside it; the sidebar never re-mounts.

0. **Login** (`/login`): sky + lockup top left. Centered white card (max 440, radius 30, `shadow-float`): mark 46px, title-lg "Sign in to Demux" / "Create your account", first name + last name side by side (sign-up only, both required; they become "Hello, [first name]"), email + password fields (labels 13/500 `ink-2`, inputs 48px, radius 12), full-width primary, a text link to switch. Then **Check your email**: 6 code boxes (56px tall, radius 12, one real `<input autocomplete="one-time-code">`), primary "Verify", "Resend code" (30 s cooldown) and "Use a different email". Trust line under the card.
0. **Landing** (`/workspaces`): opens the workspace used last in this browser, else the newest one, else **Create**.
1. **Create, connect** (`/workspaces/new` while no Gmail is connected or it needs a reconnect): centered white card (max 520, radius 30, `shadow-float`): breathing mark 56px, title-lg "Connect your Gmail", one sentence, primary "Connect with Google →", trust line. Google's errors show in the card.
2. **Create, prompt** (`/workspaces/new` once Gmail is connected): centered, top third: title-xl "Hello, [first name]" (the first name from sign-up or the profile page; just "Hello" for older accounts without one), then "What do you want to track?" 22/500 `ink-on-sky`, the prompt card (max 760), the read-only line with a lock icon. With both workspaces used, the prompt is disabled and the limit line replaces the read-only line. Build opens the new workspace in the same area.
3. **Workspace, building** (`/workspaces/[id]`, status `building`): sky + top bar (name, Building chip). Centered build card (§7.10). Nothing else.
4. **Result** (`/workspaces/[id]`, status `ready`): sky + top bar (§7.11). Body = row, gap 16, padding 0 16 16, full viewport height: **app panel** (white, radius 26, `shadow-panel`, flex 999 1 640px; the sandboxed iframe lives here) + **side panel** (glass, radius 26, flex 1 1 320px, max 380px) with Activity | Chat tabs, the activity list, and the ask input pinned to the bottom.
   - Display error banner (inside the app panel, top): bg `#FDECEA`, text `#A8321F`, "This workspace hit a display error", violet "Fix it" button.
   - Reconnect banner (under the top bar): glass card, ink text, primary button "Reconnect Gmail".
   - The side panel is a **drawer**: a ghost button in its header slides it closed (width → 0 over 300ms, the app panel takes the space); a secondary "Activity" button appears in the top bar to reopen it. Open by default from 1024px (remembered per browser), closed below 1024px where it floats over the app (`bg-white/95`).
5. **Profile** (`/profile`, from the account card): centered column (max 640), title-lg "Profile" + "Your name and the Gmail Demux reads." `ink-on-sky`, then two white cards (radius 26, `shadow-panel`, padding 24/28): **Your name** (first + last name fields side by side, both required, primary "Save" (small) on the right, "✓ Saved" `violet-ink` beside it after saving) and **Account** (sign-in email, read-only; "Gmail Demux reads" with a quiet button "Use another account" / "Connect Gmail" / "Reconnect Gmail" that goes through Google and comes back here; the read-only trust line).

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
| `flow` | background-position 0 → 200px, 1.8s linear | Gradient inside the progress bar (`background-size: 200px 100%`; the 200px tile runs violet → magenta → coral → magenta → violet so it loops without a seam) |
| `blink` | opacity steps, 1.1s | Text caret (marketing demos only) |
| `drift` | sky layer scale 1.06, translate ±2%, 40s `ease-in-out` alternate infinite | The sky backdrop on every app page. Slow enough that nobody notices it moving, only that the page isn't a flat image |
| `reveal` | fade + 16px rise, 700ms `ease-dmx-out`, stagger 80ms | Blocks entering a screen in reading order: title → card → helper line → list (`<Reveal index>`) |
| `reveal-text` | each word: fade + 0.4em rise + 8px blur → sharp, 800ms `ease-dmx-out`, stagger 45ms | Page titles only (title-xl / title-lg), at most one per screen (`<RevealText>`) |
| `pop` | fade + scale .96 + 4px from the anchor, 200ms `ease-dmx-out`, origin at the trigger | Menus and popovers |
| `drawer` | from 768px: the sidebar column's width and the panel's slide move together, 360ms `ease-dmx-out`, both ways, and the page reflows with them · below 768px: panel slides in 420ms `ease-dmx-out` (out 260ms `ease-dmx`), scrim fades 300ms · rows follow an opening panel with fade + 8px from the left, 30ms stagger; nothing animates on page load | App sidebar (§7.13). The sidebar keeps its own view-transition name so page changes never paint over it |
| UI transitions | 150–200ms `ease-dmx` | Hover, focus, tab switch |
| Hover lift | interactive cards rise 2px and their shadow deepens one step (`shadow-glass` → `shadow-panel`), 250ms; pressed: scale .99 | Workspace cards, example chips (1px) |
| Arrow nudge | trailing arrow moves 3px in its direction on hover of its button, 200ms | Build →, Continue →, Connect Gmail → |
| `page` | old: fade + 4px up + 2px blur, 160ms · new: fade + 12px rise + 4px blur → sharp, 420ms `ease-dmx-out` after 60ms | Route changes (React `<ViewTransition>`), the sky stays still |
| `step` | old: fade + 12px left, 150ms · new: fade + 16px from right, 380ms `ease-dmx-out` | Steps inside one page (sign in → code, connect → prompt) |
| Record update | 600ms fade of the violet highlight | §7.8 |

Rules:
- Entrances play once, when the screen appears. Polling and live updates never replay them.
- Never animate more than ~6 reveal steps on one screen; the whole sequence settles within 1s.
- Hover motion is for things you can click. Static content never moves on hover.
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
  /* + dmx-reveal, dmx-reveal-word, dmx-pop, dmx-drift (§9); see globals.css */
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
The iframe's CSP allows `font-src data:` only, so Google Fonts cannot load inside it. To make generated apps match:
- In the **fixed shell** (not the agent's HTML), inline Instrument Sans latin 400/500/600 as a base64 `@font-face`, with the system stack as fallback.
- `demux-base.css` exposes the same tokens as CSS variables, so the agent styles with variables, never raw hex values:
```css
:root{
  --dmx-font: "Instrument Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  --dmx-ink:#0C1A2E; --dmx-ink-2:#33445C; --dmx-ink-3:#5B6B80;
  --dmx-surface:#FFFFFF; --dmx-surface-2:#F4F7FB; --dmx-line:#E6EBF2; --dmx-line-soft:#EDF1F6; --dmx-tag:#F1F4F8;
  --dmx-accent:#6A3DF0; --dmx-accent-soft:#EEE9FE; --dmx-accent-ink:#4B24C9;
  --dmx-success-bg:#E4F5EA; --dmx-success:#1D6B37; --dmx-danger-bg:#FDECEA; --dmx-danger:#A8321F;
  --dmx-warning-bg:#FFF1E2; --dmx-warning:#8F4405; --dmx-info-bg:#E6F0FD; --dmx-info:#1F5FB8;
  --dmx-neutral-bg:#EEF2F7; --dmx-neutral:#33445C;
  --dmx-r-tag:6px; --dmx-r-card:12px; --dmx-r-col:16px;
}
```
- Generated apps are white-surface UIs. **No sky gradient and no brand gradient inside generated apps.** Violet only for the selected or updated state.
- Agent prompt rule: "Use the `--dmx-*` variables and base classes. One accent color (`--dmx-accent`). Status colors only for status."

### 10.4 Icons
Inline stroke SVG or `lucide-react`. Stroke 2px (2.2–2.4 on filled buttons), round caps and joins, sizes 14/16/18/20, color `currentColor`. Icons in use: `panel-left-open`, `panel-left-close`, `user-round`, `plus`, `chevron-down`, `chevrons-up-down`, `log-out`, `chevron-left`, `chevron-right`, `pencil`, `refresh-cw`, `undo-2`, `more-horizontal`, `arrow-right`, `arrow-up`, `check`, `lock`, `mail`. No filled or duotone icons, no emoji, no sparkles/wand/stars icons.

---

## 11. Voice and copy

- **Tone:** plain, short, concrete. Say what happened, with a real noun and a number. Sentence case. No exclamation marks.
- **Never write:** "AI-powered", "magic", "supercharge", "seamless", "unlock", "revolutionize", "✨", "Oops!".
- **Product vocabulary (fixed):** *workspace* (never "view" or "dashboard"), *prompt*, *build* (first run), *sync* (later runs), *record*, *field*, *message* (one email), *thread* (a conversation). "Live apps" is marketing-only.

| Context | Copy |
|---|---|
| Sign in | Sign in to Demux · Create your account · Check your email · We sent a 6-digit code to [email]. It expires in 10 minutes. |
| Connect | Connect your Gmail · Connect with Google · Reading from [gmail] · Use another account |
| Sidebar | Create workspace · Workspaces · No workspaces yet · Signed in as · Profile · Log out · Open sidebar / Close sidebar (labels) |
| Profile | Profile · Your name and the Gmail Demux reads. · Your name · Demux greets you by your first name. · Save · Saved · Sign-in email · Gmail Demux reads |
| Prompt page title | Hello, [first name] · What do you want to track? |
| Prompt placeholder | Describe what you want to keep track of… |
| Primary action | Build |
| Trust line | Read-only. Demux never sends or changes an email. |
| Workspace list | Workspaces · 1 of 2 |
| Limit reached | You're using both workspaces. Delete one to build another. |
| Build title | Building your workspace |
| Build phases | Understanding your request · Reading your emails · Building the interface |
| Build footer | You can close this page. Demux keeps building, and your workspace will be ready here. |
| Build failed | We couldn't build this workspace. [reason] · Try again |
| Sync status | Synced 3 min ago · Syncing… |
| Actions | Sync now · Undo · Ask for a change… |
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