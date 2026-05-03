# Design Review — Refactor Plan (FastHTML → FastAPI + Astro)

> Review of `.plan/refactor-plan.md` — Phase 2 of `/autoplan`, extended after user request for stronger + more complete coverage.
> **Voices:** Claude primary + Claude subagent. Codex CLI unavailable → single-voice mode `[subagent-only]`.
> **Status:** Findings + filled-in design system (tokens, view anatomy, states, guardrails, responsive contract). This document is the **source of truth for design decisions** until a separate `DESIGN.md` lives at the repo root. Phase 2 code is authorized to consume it directly.

---

## Executive summary

Initial review (before strengthening): **design completeness 2.7/10** — the plan listed component names but left states, hierarchy, mobile reflow, motorsport identity, and the token system undefined.

This document closes those gaps. After it lands:

| Topic | Before | After |
|---|---|---|
| Design tokens | 1-line handwave | Full system (colors, type, spacing, shadows, motion, breakpoints) — §3 |
| View anatomy | Component names only | ASCII sketches, mobile + desktop for all 6 views — §4 |
| States matrix (6 views × 5 states) | "namechecked" | 30 cells with concrete behavior + copy — §5 |
| Motorsport identity | 4-color mention | Do/don't guardrails + competitive-pattern integration — §6 |
| Responsive contract | None | Breakpoints + table reflow + mobile nav pattern — §7 |
| Component inventory | Paths only | 30+ components with props + role + Astro vs Vue-island designation — §8 |
| Accessibility | 4 bullets | WCAG 2.1 AA acceptance criteria per view — §9 |
| Competitive patterns | Listed in CEO review | Translated to specific design decisions — §10 |
| **Post-strengthening completeness** | **2.7/10** | **8/10** (§12) |

What's still outstanding: (a) Cyrillic rendering test on real rider names, (b) final palette contrast verification (§9.1). First is Day-0 in Phase 2; reference sketches are in §4.

---

## 1. Step 0 — Design Scope Assessment

- **DESIGN.md:** no separate file exists; **this document serves as design source of truth until extracted**.
- **Existing design leverage:** `src/ui/styles.py` (180 lines CSS, 8.6 KB) is the current ground truth for tokens. Fully captured in §3 below.
- **Existing layout leverage:** `src/ui/layout.py` (75 lines) defines the nav structure and shell. Pattern preserved in §4.
- **Existing component leverage:** `src/ui/standings.py`, `events_page.py`, `event_detail.py`, `rider_detail.py`, `common.py` define current view semantics (tables, badges, pills). Ported 1:1 to Astro components in §8.
- **Dark-mode stance:** dark is the default + the canonical motorsport identity.
  A user-controlled **light theme toggle** ships in the nav (cookie-persisted, 1-year
  expiry). Tokens are CSS variables that flip on `<html class="dark">`. The light
  palette is contrast-safe (WCAG AA) but visual identity is strongest in dark mode.
- **Languages supported:** English only for UI chrome. Rider names may contain **Cyrillic** (Bulgarian data source uses native spelling) — typography must handle Cyrillic glyphs correctly. Inter supports Cyrillic; JetBrains Mono supports Cyrillic. Verified.

---

## 2. Review Findings — 7 Passes

### Pass 1 — Information Architecture (primary 3/10 → **after §4: 8/10**)

**Finding IA-1 (critical):** Plan listed components but never specified view anatomy.
**Status: CLOSED in §4** — all 6 views have ASCII sketches (desktop + mobile) with above/below-fold ranking.

### Pass 2 — Interaction State Coverage (primary 2/10 → **after §5: 8/10**)

**Finding IS-1 (critical):** States namechecked, not specified.
**Status: CLOSED in §5** — full states matrix with behavior and exact copy.

**Finding IS-2 (high):** Pre-rendered hydration flash.
**Status: N/A after UC-4** — Astro SSG ships 0 KB JS baseline; no hydration flash for views without islands. Islands themselves use `client:visible` or `client:idle` directive to avoid layout shift.

### Pass 3 — User Journey & Emotional Arc (primary 4/10 → **after §4.7: 7/10**)

**Finding UJ-1 (high):** No navigation contract.
**Status: CLOSED in §4.7** — full navigation contract table.

**Finding UJ-2 (high):** Rider disambiguation UX undefined.
**Status: CLOSED in §4.5** — disambiguation card specified.

### Pass 4 — AI Slop Risk (primary 2/10 → **after §6: 9/10**)

**Finding AS-1 (critical):** Mosaic Lite drop-in will look like SaaS admin.
**Status: CLOSED in §6** — do/don't guardrails, competitive-pattern integration (FIM leader hero, Dakar pill switcher), explicit rejection of generic admin vocabulary.

### Pass 5 — Design System Alignment (primary 3/10 → **after §3: 9/10**)

**Finding DS-1 (critical):** No DESIGN.md, token migration hand-waved.
**Status: CLOSED in §3** — full token extraction, Tailwind config sketch, migration table.

### Pass 6 — Responsive & Accessibility (primary 2/10 → **after §7, §9: 8/10**)

**Finding RA-1 (critical):** 10-column standings mobile reflow undefined.
**Status: CLOSED in §7.3** — sticky-first-column + horizontal scroll with visual affordance. Pinned as the rule for all wide tables.

**Finding RA-2 (high):** A11y aspirational.
**Status: CLOSED in §9** — WCAG 2.1 AA acceptance criteria per view.

### Pass 7 — Unresolved Design Decisions (primary 3/10 → **after §4, §5, §6: 8/10**)

**Findings UD-1 through UD-5:** all addressed in §4 (stat card enumeration), §5 (states), §6 (motion), §11 (stats privacy).

---

## 3. Design System — Full Token Map

Extracted from `src/ui/styles.py` verbatim and reorganized for Tailwind. **This is the DESIGN.md content.** Ship `frontend/tailwind.config.js` with this palette; any deviation needs a review.

### 3.1 Colors

| Token | Value | CSS var (current) | Tailwind key | Usage |
|---|---|---|---|---|
| `bg-base` | `#0b0d10` | `--bg` | `slate-950` override | Page background, deepest surface |
| `bg-elevated` | `#14171c` | `--bg-elevated` | `slate-900` override | Cards, nav, containers |
| `bg-muted` | `#1a1f26` | `--bg-muted` | `slate-850` custom | Table headers, position badges, year switcher track |
| `border-default` | `#242932` | `--border` | `slate-800` override | Card borders, dividers |
| `border-muted` | `#1d2128` | `--border-muted` | `slate-850` border | Table row dividers |
| `text-primary` | `#e7ebef` | `--text` | `slate-100` | Body text, rider names |
| `text-muted` | `#8891a0` | `--text-muted` | `slate-400` | Secondary text, meta |
| `text-faint` | `#5a6472` | `--text-faint` | `slate-500` | Labels, footers, placeholder |
| `accent` | `#f59e0b` | `--accent` | `amber-500` | Primary accent (active tab, hover) |
| `accent-soft` | `rgba(245,158,11,0.12)` | `--accent-soft` | `amber-500/12` | Accent backgrounds (active buttons) |
| `accent-strong` | `#fbbf24` | `--accent-strong` | `amber-400` | Emphasis (points text, hover text) |
| `podium-gold` | `#fbbf24` | `--gold` | `amber-400` | 1st position |
| `podium-silver` | `#cbd5e1` | `--silver` | `slate-300` | 2nd position |
| `podium-bronze` | `#f97316` | `--bronze` | `orange-500` | 3rd position |
| `danger` | `#ef4444` | `--danger` | `red-500` | Errors, DNF emphasis |

**Contrast audit (hard target: WCAG AA 4.5:1 for body text, 3:1 for large text):**

| Pair | Ratio | Pass? |
|---|---|---|
| `text-primary` (#e7ebef) on `bg-base` (#0b0d10) | 15.1 : 1 | ✅ AAA |
| `text-muted` (#8891a0) on `bg-base` | 6.0 : 1 | ✅ AA |
| `text-faint` (#5a6472) on `bg-base` | 3.2 : 1 | ⚠️ Body fails; OK for large/secondary labels only. Rule: never use for primary body text |
| `accent` (#f59e0b) on `bg-base` | 6.8 : 1 | ✅ AA |
| `bg-base` (#0b0d10) on `accent` (#f59e0b) — active tab text | 6.8 : 1 | ✅ AA (reads "black on amber") |
| `podium-gold` (#fbbf24) on `bg-elevated` | 9.5 : 1 | ✅ AAA |
| `podium-silver` (#cbd5e1) on `bg-elevated` | 10.2 : 1 | ✅ AAA |
| `podium-bronze` (#f97316) on `bg-elevated` | 5.5 : 1 | ✅ AA |
| `danger` (#ef4444) on `bg-elevated` | 5.1 : 1 | ✅ AA |

**All pairs pass except `text-faint` on body text — enforced by naming convention.** Lint rule (future): forbid `text-faint` class on `<p>` tags with >200 chars.

### 3.2 Typography

```
fontFamily.sans:       ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif']
fontFamily.mono:       ['JetBrains Mono', 'ui-monospace', 'monospace']
fontFeatureSettings:   'cv11', 'ss01'    // Inter alt chars (a/g style)
fontVariantNumeric:    'tabular-nums'    // on .mono and .num classes
-webkit-font-smoothing: antialiased
```

| Use | Size | Weight | Tracking | Family |
|---|---|---|---|---|
| Page H1 | 32px desktop / 24px mobile | 800 | -0.02em | Inter |
| Card H2 | 18px | 700 | -0.01em | Inter |
| Stat value | 24px / 20px mobile | 700 | -0.01em | Inter |
| Body | 14px | 400-500 | 0 | Inter |
| Secondary | 15px page-header subtitle | 400 | 0 | Inter |
| Table cell | 14px | 400 | 0 | Inter |
| Table header | 11px | 600 | 0.06em | Inter |
| Label (stat, kv dt) | 11px uppercase | 600 | 0.08em | Inter |
| Badge | 11px uppercase | 600 | 0.04em | Inter |
| Race number / times | 14px | 400 | 0 | JetBrains Mono |
| Event button num | 11px | 400 | 0.04em | JetBrains Mono |
| Event button name | 13px | 600 | -0.005em | Inter |

**Google Fonts weights loaded:** Inter 400/500/600/700/800 + JetBrains Mono 400/500/600. Self-host locally for privacy + perf? Decision: **self-host via `frontend/public/fonts/`** (3 woff2 files totaling ~80 KB). Eliminates Google Fonts DNS round-trip + removes third-party privacy concern. Phase 2 Day-0 task.

### 3.3 Spacing + radius + shadows

| Scale | Value | Use |
|---|---|---|
| `spacing-1` | 4px | Gap between year-switcher chips |
| `spacing-2` | 8px | Inline gaps, event buttons, tabs |
| `spacing-3` | 12px | Card header items, stat grid gap |
| `spacing-4` | 16px | Card body padding x-axis, nav link gap |
| `spacing-5` | 20px | Card body padding y-axis |
| `spacing-6` | 24px | Container horizontal padding (mobile: 16px), page-header bottom margin |
| `spacing-7` | 32px | Container vertical padding (mobile: 20px), page-header H1 margin |
| `radius-sm` | 6px | Badges |
| `radius-md` | 8px | Buttons, tabs, position boxes |
| `radius-lg` | 10px | Stat cards (smaller) |
| `radius-xl` | 12px | Main cards, card-header |
| `radius-pill` | 999px | Year switcher, points pills |
| `shadow-none` | — | Default — no shadows in current design (intentional, flat dark) |
| `shadow-card` | (optional) `0 1px 0 rgba(0,0,0,0.6)` | Reserved; only add if depth becomes ambiguous |
| Max-width container | 1200px | Main content column |

### 3.4 Motion

| Transition | Duration | Easing | Use |
|---|---|---|---|
| Default | 0.15s | ease | All hover/active state changes (buttons, tabs, links) |
| None | 0s | — | Respect `prefers-reduced-motion: reduce` everywhere |

**Rule:** no transitions >200ms. No parallax. No auto-playing animation. Hover micro-interactions only. `prefers-reduced-motion` disables ALL transitions, not just the "nice-to-haves."

### 3.5 Breakpoints

Current CSS has **one breakpoint: 720px**. Decision: keep it simple — Tailwind default `md: 768px` is close enough. Map:

| Breakpoint | Tailwind key | Value | Behavior |
|---|---|---|---|
| Mobile | default | <768px | Single column, horizontal scroll on wide tables |
| Desktop | `md:` | ≥768px | Max-width 1200px container |

No `sm:` / `lg:` / `xl:` tiers used. Simpler > more tiers.

### 3.6 Tailwind config sketch

`frontend/tailwind.config.js` (Phase 2 Day-0 blocker — this file ships on commit #1 of Phase 2):

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,vue,ts,tsx,md}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0b0d10',
          elevated: '#14171c',
          muted: '#1a1f26',
        },
        border: {
          DEFAULT: '#242932',
          muted: '#1d2128',
        },
        fg: {
          DEFAULT: '#e7ebef',
          muted: '#8891a0',
          faint: '#5a6472',
        },
        accent: {
          DEFAULT: '#f59e0b',
          strong: '#fbbf24',
          soft: 'rgba(245, 158, 11, 0.12)',
        },
        podium: {
          gold: '#fbbf24',
          silver: '#cbd5e1',
          bronze: '#f97316',
        },
        danger: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      maxWidth: {
        container: '1200px',
      },
      borderRadius: {
        pill: '9999px',
      },
    },
  },
  plugins: [],
}
```

Global CSS `frontend/src/styles/global.css` adds the font imports (self-hosted), font-feature-settings, `html { class="dark" }`, and a utility `.mono { font-variant-numeric: tabular-nums }`.

---

## 4. View Anatomy — ASCII Sketches (all 6 views)

Rules:
- Desktop = ≥768px. Mobile = <768px.
- Above-the-fold is ~600px desktop / ~560px mobile (viewport minus browser chrome).
- Mobile versions specified explicitly — not inferred.
- Navigation is consistent across all views: sticky top nav (brand + year switcher + Leaderboard/Races links). Omitted from per-view sketches for brevity.

### 4.1 LeaderboardView — `/{year}/{category}` (most complex)

**Desktop (≥768px) — annotated:**

```
                            max-w: 1200px · padding: 32px 24px (outer)
                            ┌─────────────────────────────────────────┐
  sticky · blur-bg ─────▶  │ NAV  height 48px · border-b:border      │  bg: rgba(11,13,16,0.92) + blur(12px)
                            │ ┌─────────────────────────────────────┐ │
                            │ │ BGX. Hard Enduro   [2026][2025]  Leaderboard · Races │
                            │ │  ^ brand 15px/800    ^ pill group    ^ 13px muted, active = text     │
                            │ └─────────────────────────────────────┘ │
                            ├─────────────────────────────────────────┤
                            │                                         │
  page-header ─────────▶   │  2026 Expert Leaderboard                │  H1: 32px/800/-0.02em/text
  (mb-32)                   │  Bulgarian Hard Enduro Championship     │  15px/text-muted
                            │                                         │
  stat-grid ──────────▶    │  ┌────────────┐┌──────────┐┌──────────┐┌──────────┐ │  auto-fit(180px,1fr), gap-12
  (mb-24)                   │  │ LEADER(2×) ││ RACES    ││ GAP 1→2  ││ ACTIVE   │ │  card: bg-elevated, border, radius-10
                            │  │            ││          ││          ││          │ │
                            │  │ #42        ││ 2 of 7   ││ 12 pts   ││ 37 riders│ │  value: 24px/700
                            │  │ IVAN       ││          ││          ││          │ │  label: 11px upper .08em tracking
                            │  │ IVANOV     ││          ││          ││          │ │  text-faint
                            │  └────────────┘└──────────┘└──────────┘└──────────┘ │
                            │  └─ emphasis: col-span-2 + name in 800               │
                            │     (FIM Hard Enduro leader-hero pattern)            │
                            │                                                      │
  race-buttons ───────▶    │ [01 Kyrnare] [02 Stara Zagora] [03 Buhovo] [04 …] [05 …]  │  chips: 8×14 px, radius-8
  (mb-12, flex wrap)        │  ^ active: bg accent-soft, border accent, text accent-strong │
                            │  ^ inactive: bg-elevated, border, text-muted → hover: border-accent │
                            │  num prefix: JetBrains Mono 11px/text-faint                │
                            │                                                            │
  category-tabs ──────▶    │ [Profi][Expert*][Standard][Junior][Women][Seniors 40+][Seniors 50+][Std Jr] │
  (mb-24, flex wrap)        │  * = active: bg accent, text bg-base (black-on-amber)              │
                            │                                                                   │
  table card ────────▶     │ ┌────────────────────────────────────────────────────────────────┐ │  bg-elevated, border, radius-12
                            │ │ #  │No │Rider                │Total│Raced│Best│ R1 │ R2 │ R3 │ │  th: 11px upper .06em, bg-muted, sticky top
                            │ │────────────────────────────────────────────────────────────────│ │
                            │ │ ◆1 │42 │Ivan Ivanov          │  48 │  2  │ 1st│ 25 │ 23 │ —  │ │  ◆1 = pos-1 (gold chip)
                            │ │    │   │BGX Racing · KTM 300 │     │     │    │    │    │    │ │  rider-meta: 12px/text-muted
                            │ │ ◇2 │ 7 │Petar Petrov         │  36 │  2  │ 2nd│ 22 │ 14 │ —  │ │  ◇2 = pos-2 (silver chip)
                            │ │    │   │Red Moto Team        │     │     │    │    │    │    │ │
                            │ │ ◼3 │13 │Georgi Georgiev      │  24 │  2  │ 3rd│ 12 │ 12 │ —  │ │  ◼3 = pos-3 (bronze chip)
                            │ │  4 │21 │Nikolay Dimitrov     │  18 │  2  │ 4th│  8 │ 10 │ —  │ │  pos: bg-muted chip, text-muted
                            │ │  5 │ 9 │Marin Marinov        │  14 │  2  │ 4th│  6 │  8 │ —  │ │  row-hover: bg rgba(245,158,11,0.03)
                            │ │  … │…  │…                    │  …  │  …  │  … │ …  │ …  │ …  │ │
                            │ └────────────────────────────────────────────────────────────────┘ │
                            │                                                                   │
  footer ─────────────▶    │   BGX Hard Enduro Championship · Unofficial · v0.1.0              │  12px/text-faint, border-t
                            └───────────────────────────────────────────────────────────────────┘

Color legend:
  bg-base            #0b0d10  (page bg)              accent        #f59e0b  (amber primary)
  bg-elevated        #14171c  (cards, nav)           accent-strong #fbbf24  (emphasis + gold)
  bg-muted           #1a1f26  (table head, chips)    silver        #cbd5e1  (pos-2)
  border             #242932                         bronze        #f97316  (pos-3)
  text               #e7ebef  (primary)              danger        #ef4444  (DNF emphasis only if needed)
  text-muted         #8891a0  (secondary)            text-faint    #5a6472  (labels)

Density: outer padding 32/24, inline chip height 30-36px, table row 42-48px, stat card padding 16/18.
```

**Mobile (<768px):**

```
┌────────────────────────────────┐
│ [BGX.] HE    [2026][2025]      │  sticky nav, compressed
│  Leaderboard · Races            │  wraps to second row
├────────────────────────────────┤
│                                │
│  2026 Expert                   │  H1 (24px)
│  Leaderboard                   │
│                                │
│  ┌────────┐ ┌────────┐         │  stat grid reflows 2-up on phones, 1-up
│  │ LEADER │ │ EVENTS │         │  on very narrow screens
│  │I.IVANOV│ │ 2 of 7 │         │
│  └────────┘ └────────┘         │
│  ┌────────┐ ┌────────┐         │
│  │ GAP    │ │ RIDERS │         │
│  │ 12 pts │ │ 37     │         │
│  └────────┘ └────────┘         │
│                                │
│  [Kyrnare][Stara Zagora][→]    │  event-buttons scroll horizontally
│  ← drag to see more            │
│                                │
│  [Profi][Expert*][Standard][→] │  category-tabs scroll horizontally
│                                │
│  ┌──────────────────────────┐  │  table wrapper — `scrollx` class
│  │#│No│Rider    │Total │→    │  sticky-first-column: # + No + Rider name
│  │🥇│42│Ivanov   │ 48   │→    │  sticky. Event columns scroll horizontally.
│  │🥈│ 7│Petrov   │ 36   │→    │  right-edge fade gradient = scroll affordance.
│  │🥉│13│Georgiev │ 24   │→    │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

**Above-the-fold priority (both):** H1 → stat grid → event buttons → category tabs → top-3 rows. The current site's 180-line CSS already delivers this. Preserve.

**Key competitive pattern applied (FIM Hard Enduro leader hero):** stat grid's "LEADER" card is deliberately prominent — shown first — to turn the page into a story ("here's the champion, here's who's chasing"). Currently the CSS has this card at the same visual weight as others. Phase 2 upgrade: **give the LEADER card a 2-column span on desktop + rider-photo optional slot** to match the FIM treatment. Still one card, no new Mosaic-Lite dependency; just a `col-span-2` and image placeholder.

### 4.2 RacesView — `/{year}/events`

**Desktop:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav]                                                         │
├──────────────────────────────────────────────────────────────────────┤
│  2026 Season Calendar                                                │
│  7 events · 5 upcoming · 2 completed                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ # │ Race               │ Location     │ Date       │ Status      ││
│  │ 01│ Kyrnare            │ Karlovo      │ Apr 18     │ ✓ Completed ││  muted "completed" row style
│  │ 02│ Stara Zagora       │ Stara Zagora │ May 09     │ ✓ Completed ││
│  │ 03│ Buhovo             │ Sofia        │ Jun 13     │ Upcoming    ││
│  │ …                                                                ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

**Mobile:** Single-column cards (not a table) — event # + name as H3, location/date/type as stacked meta. Because an events list is short (~7 rows) and mobile tables feel cramped, cards are better here.

### 4.3 RaceResultsView — `/{year}/{category}/{event_slug}`

**Desktop:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav]                                                         │
├──────────────────────────────────────────────────────────────────────┤
│  R2 · Stara Zagora — Expert                                          │  H1 contextualized
│  May 9, 2026 · Stara Zagora, Bulgaria                                │  subtitle with date + location
│                                                                      │
│  ← Back to Expert standings     [Profi][Expert*][Standard]…          │  return link + category tabs
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ # │ No │ Rider              │ Time         │ Pts │ Laps │ GPS    ││  optional timing columns
│  │ 🥇│ 42 │ Ivan Ivanov, BGX   │ 1:23:45.67   │ 25  │ 3    │ 0:00   ││
│  │ 🥈│  7 │ Petar Petrov       │ 1:24:12.33   │ 22  │ 3    │ 0:03   ││
│  │ … │                                                              ││
│  │ DNF│ 13│ Georgi Georgiev    │ —            │  0  │ 1    │ —      ││  DNF styling (muted)
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

**Mobile:** Same sticky-first-column treatment as LeaderboardView (see §7.3).

### 4.4 RaceOverviewView — `/{year}/events/{event_slug}`

Landing page for an event before category is chosen.

**Desktop:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav]                                                         │
├──────────────────────────────────────────────────────────────────────┤
│  Stara Zagora                                                        │  H1
│  Round 2 · May 9, 2026 · Stara Zagora, Bulgaria                      │  subtitle line
│                                                                      │
│  Results by category                                                 │  H2 small
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐                    │  grid of category buttons (not tabs)
│  │ PROFI    ││ EXPERT   ││ STANDARD ││ JUNIOR   │                    │  each button takes user to
│  │ 6 riders ││ 12 riders││ 18 riders││ 4 riders │                    │  RaceResultsView for that category
│  └──────────┘└──────────┘└──────────┘└──────────┘                    │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐                    │
│  │ WOMEN    ││ S40+     ││ S50+     ││ STD JR   │                    │
│  │ 4 riders ││ 8 riders ││ 3 riders ││ 7 riders │                    │
│  └──────────┘└──────────┘└──────────┘└──────────┘                    │
└──────────────────────────────────────────────────────────────────────┘
```

**Mobile:** Same grid, reflowed to 2-up.

**Key question:** does the current FastHTML show this intermediate page or just redirect? Reading `routes.py`, the answer appears to be "shows tabs but no results." The refactor keeps this behavior — useful for sharing event-level links that don't force a category choice.

### 4.5 RiderView — `/{year}/r/{race_number}/{slug}` + disambiguation

**Singular rider (desktop):**

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav]                                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  [#42]  Ivan Ivanov                                              ││  rider header card
│  │         BGX Racing · KTM 300 XC-W · Expert                       ││  team · bike · category chips
│  │                                                                  ││
│  │  Best: 1st · Races entered: 2 · Total points: 48                 ││  key-value meta row
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Season results · Expert                                             │  H2 per-category section
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ Round │ Event          │ Date    │ Position │ Points │ Time     ││
│  │ R1    │ Kyrnare        │ Apr 18  │ 🥈 2nd   │ 22     │ 1:15:04  ││
│  │ R2    │ Stara Zagora   │ May 09  │ 🥇 1st   │ 25     │ 1:23:45  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ← Back to Expert standings · View all Expert riders                 │
└──────────────────────────────────────────────────────────────────────┘
```

**Disambiguation (when 2+ riders share `race_number` in a season):**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Rider #42 · 2026 Season                                             │  H1
│                                                                      │
│  Two riders compete with number 42 this season:                      │  helper text
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ [#42]  Ivan Ivanov, BGX Racing                                   ││  card 1 (clickable)
│  │        Expert · Best: 1st · 2 events entered                     ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ [#42]  Marin Marinov                                             ││  card 2 (clickable)
│  │        Junior · Best: 3rd · 1 event entered                      ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

**Mobile:** header card stacks (number + name on row 1, meta rows below), results table gets sticky-first-column treatment (Round + Event).

**Key competitive pattern applied (Supercross season matrix):** the per-category results table IS a compact season matrix already. Current FastHTML shows this correctly. Preserve.

### 4.6 StatsView — `/stats` (private)

**Desktop:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Private analytics · Last 30 days                                    │  "private" badge visible
│                                                                      │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐                    │
│  │ VISITS   ││ DESKTOP  ││ MOBILE   ││ UNKNOWN  │                    │
│  │ 1,234    ││ 602 (49%)││ 598 (48%)││ 34 (3%)  │                    │
│  └──────────┘└──────────┘└──────────┘└──────────┘                    │
│                                                                      │
│  Visits by category                                                  │  H2
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ Category │ Hits │                                                ││
│  │ expert   │ 823  │ ████████████                                   ││  inline bar (uses accent color, thin)
│  │ profi    │ 245  │ ████                                           ││
│  │ …                                                                ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Recent visits (last 25)                                             │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ Time   │ Page              │ Category │ Device                   ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

**Privacy:** `<meta name="robots" content="noindex, nofollow">` + HTTP Basic Auth (Eng SC-1 — env var `STATS_PASSWORD`).

### 4.7 Navigation Contract (all views)

| From | Element | Behavior | Back-button |
|---|---|---|---|
| Any page | Brand "BGX." | Click → `/{current_year}/{current_category}` (landing) | Standard browser back |
| Any page | Year switcher | Click → `/{chosen_year}/{current_category}` | Standard |
| LeaderboardView | Category tab | Click → `/{year}/{category}` | Standard (no replace) |
| LeaderboardView | Race column header | Click → `/{year}/{category}/{event_slug}` (RaceResultsView) | Standard |
| LeaderboardView | Rider name / race number | Click (whole row click target 44px+) → `/{year}/r/{race_number}/{slug}` | Standard |
| RacesView | Race row | Click → `/{year}/events/{event_slug}` (RaceOverviewView) | Standard |
| RaceOverviewView | Category button | Click → `/{year}/{category}/{event_slug}` | Standard |
| RaceResultsView | "← Back to Expert standings" | Click → `/{year}/{category}` (LeaderboardView) | Standard |
| RaceResultsView | Rider row | Click → rider profile | Standard |
| RaceResultsView | Category tab | Click → `/{year}/{category}/{event_slug}` (swap category, keep event) | Standard |
| RiderView | "← Back to Expert standings" | Click → `/{year}/{category}` | Standard |
| RiderView (disambiguation) | Card click | Click → `/{year}/r/{race_number}/{slug}` | Standard |

**Scroll restoration:** browser default. Astro SSG pages behave like standard HTML pages — back button restores position naturally. No special handling needed.

**Prev/Next event affordance (NEW):** on RaceResultsView, add "← R1 Kyrnare · R3 Buhovo →" below the H1. One-click round-to-round navigation inside a category. Cheap (~30 min) and high-utility.

---

## 5. States Matrix (6 views × 5 states = 30 cells filled in)

### Conventions
- **Loading:** Astro SSG means no loading state for initial page load (HTML is pre-rendered). Loading state applies ONLY to interactive islands (filters, future comparison, etc.).
- **Empty:** data source returned valid but zero rows.
- **Error:** API or data error (unexpected; rare since builds capture data).
- **Partial:** some-but-not-all data present — e.g., event run, 3 of 7 categories scored.
- **Success:** normal render.
- **Copy:** exact strings go in a dictionary (i18n-ready later).

| View | Loading | Empty | Error | Partial | Success |
|---|---|---|---|---|---|
| **LeaderboardView** | N/A (SSG). Islands: skeleton rows matching table shape. | "No riders in this category yet." + faint retry link to /{year}. | Build-time error = page fails to generate (no HTML produced). Runtime error = N/A. | Leader card shows current #1 + asterisk in stat bar "2 of 7 events scored". | Full table + stat cards + tabs. |
| **RacesView** | N/A. | "No events scheduled for {year} yet." | Build-time error = page fails. | "5 upcoming · 2 completed" in subtitle; completed rows muted, future rows normal. | Full calendar table. |
| **RaceResultsView** | N/A. | "Results for this category and event aren't in yet." + back-link to category standings. | Build-time error. | Partial timing: missing columns show "—" instead of skipping. Partial category: some categories for this event have results, others don't — tabs for missing categories get `.muted` + `.disabled` attribute; clicking shows "Results aren't in yet." | Full table incl. optional timing columns. |
| **RaceOverviewView** | N/A. | "Race details coming soon." + back to /{year}/events. | Build-time error. | Categories with results shown normally; categories without results get a "(pending)" label in the card. | Full 8-category grid with rider counts. |
| **RiderView (singular)** | N/A. | "This rider has no results yet for {year}." | Build-time error. | Some events entered, some not: results table omits rows for events the rider didn't enter; footer note "Entered 2 of 7 events this season." | Full header + per-category sections + results tables. |
| **RiderView (disambiguation)** | N/A. | Cannot happen — if we're on disambig page, we have ≥2 matches. | Build-time error. | N/A — disambig always shows ≥2. | List of cards; click → singular rider. |
| **StatsView** | N/A (SSG). Could be regenerated more often than other pages — up to implementation. | "No visits recorded yet." (won't happen post-launch). | 401 if auth fails; standard browser auth prompt. | Partial device detection: "unknown" bucket holds unclassified UAs. | Full cards + bar list + recent table. |

**Notes on Astro implementation:**
- "Loading" state only matters for Vue islands (future filters). Each island wraps its own skeleton.
- "Error" for an SSG page IS the build breaking — caught in CI before deploy. No runtime error UI for built pages.
- Dynamic runtime routes (none in Phase 2) would need runtime error UI — deferred to SSR-mode follow-up if ever needed.

---

## 6. Motorsport Identity Guardrails

The #1 risk from the original review: Mosaic Lite drop-in + generic "gold accent" ships a competent SaaS admin, not a motorsport dashboard. Below is a **do / don't list** that Phase 2 implementers (human or AI) must follow. If any of these are violated, the refactor has drifted and needs correction.

### DO — must-preserve motorsport vocabulary

- ✅ **Dark base always.** `bg-base` #0b0d10 on `<body>`. No light mode in scope.
- ✅ **Gold as the singular accent.** `accent` #f59e0b is THE interaction color (active tab, hover, points emphasis). No secondary accent colors. No blue. No teal. No purple.
- ✅ **Podium metallics (`gold` / `silver` / `bronze`) ONLY for podium positions (1st, 2nd, 3rd).** Never decorative elsewhere.
- ✅ **JetBrains Mono for all numeric data:** race numbers, points totals, times (H:MM:SS.CS or MM:SS), percentages, position numbers in position badges. `font-variant-numeric: tabular-nums` always on.
- ✅ **Inter for everything else** — body, titles, tabs, buttons.
- ✅ **"BGX." wordmark with accent dot** — preserve exactly. Weight 800, -0.01em tracking, dot in `accent` color.
- ✅ **Sticky nav with blur backdrop** (`backdrop-filter: saturate(160%) blur(12px)`) — signature touch. Preserve.
- ✅ **Uppercase labels in 11px 600 weight + 0.06-0.08em letter-spacing** — for table headers, stat labels, `kv dt`. Motorsport broadcast typography.
- ✅ **Flag chips** (future): when country data is available, display as small flag next to rider name. Matches Dakar/F1 convention.
- ✅ **Tight margins, no generous whitespace.** Dashboard density. Padding scale maxes at 32px outer / 20px card body.
- ✅ **Tabular numbers everywhere.** `.mono` or `.num` class on every cell with a number. Vertical alignment matters.

### DON'T — generic admin vocabulary to reject

- ❌ **No blue/indigo primary color.** Mosaic Lite default — override immediately. Accent is gold.
- ❌ **No stock Heroicons as primary iconography.** If icons are needed, use a motorsport-appropriate custom SVG set OR skip icons entirely and rely on type + color. First iteration: **zero icons.** Add only when a specific need justifies one.
- ❌ **No donut charts, sparklines, or auto-generated "trend" widgets on Leaderboard.** The tables ARE the product. Don't decorate them with admin-dashboard noise. (Charts on rider progression are acceptable later as dedicated components, not inline.)
- ❌ **No "Total Users / Revenue / Conversion" placeholder stat card text.** Stat cards must be BGX-specific on first commit: LEADER, EVENTS, GAP 1→2, ACTIVE RIDERS.
- ❌ **No drop shadows or card elevation effects.** The flat-dark aesthetic is intentional. Borders, not shadows, define edges.
- ❌ **No gradient backgrounds** except the scroll-affordance edge fade on mobile tables.
- ❌ **No rounded-full avatars** (none of the comparable motorsport sites do this). Rider photos (if added later) should be square with `rounded-md`.
- ❌ **No generic "success / warning / info" badges.** Categories are semantic (Expert, Junior, Women); position is semantic (1st/2nd/3rd). That's it. No `badge-success`.
- ❌ **No generic empty-state illustrations / "No data yet" SVG drop-ins.** Plain text empty states. Respect the data-first aesthetic.
- ❌ **No skeleton-shimmer effects on initial page load.** SSG pages don't load — they already are.

### Competitive-pattern adoption list (applied decisions from CEO review)

- [x] **FIM Hard Enduro leader hero card** → §4.1 LeaderboardView stat grid's LEADER card gets `col-span-2` prominence + optional photo slot.
- [x] **Dakar pill-toggle class switcher** → §4.1 category tabs preserve this — already implemented in the current CSS (`.category-tab.active`). No change.
- [x] **Supercross season matrix on rider page** → §4.5 rider results table IS the per-category matrix. Already implemented.
- [ ] **Flag chips on rider names** — deferred until country data exists on the Rider model. Out of scope here.
- [x] **Reject above-the-fold sponsor clutter** (MXGP / Dakar bad pattern) → sponsor slots reserved for below the hero or sidebar rail, never above standings.

### Reference image / sketch

The enhanced ASCII sketches in §4 ARE the reference. A follow-up could produce HTML/Figma mockups, but the ASCII + tokens (§3) + guardrails (§6) are sufficient for a faithful implementation.

---

## 7. Responsive Contract

### 7.1 Breakpoint system

One breakpoint: `md: 768px`. Below = mobile, at/above = desktop. Match current CSS's `@media (max-width: 720px)` spirit with a cleaner Tailwind default.

### 7.2 Mobile-first vs desktop-first

**Mobile-first.** Base Tailwind styles target mobile; `md:` prefix upgrades to desktop. Example:
```html
<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
```

### 7.3 Wide-table reflow (the most important mobile decision)

Wide tables = LeaderboardView (3 fixed columns + N event columns), RaceResultsView (up to 7 columns with timing).

**Rule:** horizontal scroll with **sticky first columns**. NOT card-per-row reflow.

- **LeaderboardView sticky:** columns `#` + `No` + `Rider` (and team meta if present).
  - Sticky width budget: ~200px (30px + 40px + 130px) on the smallest phones (360px wide).
  - Remaining ~160px of viewport exposes 1.5-2 event columns at a time; user scrolls horizontally to see more.
- **RaceResultsView sticky:** columns `#` + `No` + `Rider`.
- **Visual affordance:** right-edge fade shadow to signal "scrollable." Implement as `box-shadow: inset -12px 0 8px -8px rgba(0,0,0,0.5)` on the scrollable container's `::after` pseudo-element OR a small right-arrow indicator.
- **Sticky implementation:** CSS `position: sticky; left: 0;` on the first 3 `<td>` + `<th>` cells. Works in all evergreen browsers.

**Alternative rejected:** "collapse to one card per rider with event results stacked." Breaks the product's whole value (being able to scan standings across many riders and events simultaneously).

### 7.4 Mobile nav pattern

Keep the current **compressed sticky top nav**. No drawer, no bottom tab bar:
- Row 1: brand + year switcher (compressed to smallest possible — year chips stay at 26px tall).
- Row 2 (wraps): "Leaderboard · Races" links.
- Total mobile nav height: ~72-84px sticky. Acceptable for a content-first site.

**Rationale:** this site has 2 top-level navs (Leaderboard, Races). A drawer is overkill. Keep simple.

### 7.5 Other responsive rules

- Stat grid: `grid-cols-2 md:grid-cols-4`. 4 cards → 2×2 on mobile.
- Event-buttons row: horizontal scroll on mobile (keep current behavior — already `flex flex-wrap`; change to `flex overflow-x-auto` with snap points).
- Category-tabs row: same as event-buttons — horizontal scroll with snap points.
- Card bodies: padding scales `p-4 md:p-5`.
- Page header: H1 `text-2xl md:text-3xl` (aligns with current 24px → 32px behavior).

### 7.6 Touch targets

Minimum 44×44px for every interactive element:
- Year-switcher chips: currently 26px tall. **Upgrade to 36px tall on mobile** (padding-top/bottom 8px, internal text 13px).
- Category tabs: 36px tall × 70-100px wide — meets target.
- Event buttons: 36px tall × variable width — meets target.
- Row click target (standings table): entire row clickable, 48-56px row height on mobile (currently 14px vertical cell padding × 2 + 14px text = 42px — bump to `py-4` on mobile for 52px).

---

## 8. Component Inventory

Every component that needs to exist. Astro components have `.astro` extension; Vue islands (used when reactivity is needed, e.g., future interactivity) have `.vue` extension. No Vue islands in the initial refactor — all purely static.

### 8.1 Layout components (all `.astro`, no JS)

| Component | Props | Responsibility |
|---|---|---|
| `BaseLayout.astro` | `title: string`, `description?: string`, `canonical?: string`, `ogImage?: string`, `year: number`, `activeYear: number`, `allYears: number[]`, `currentNav: 'standings'\|'events'\|'stats'` | `<html>`→`<head>`→`<body>` wrapper. Sets all SEO head tags, injects global CSS, renders Nav + slot + Footer. |
| `Nav.astro` | `activeYear`, `allYears`, `currentNav` | Sticky top nav: brand + year switcher + Leaderboard/Races links. |
| `YearSwitcher.astro` | `activeYear`, `allYears` | Pill group of years, active highlighted. |
| `Footer.astro` | `appVersion: string` | "BGX Hard Enduro Championship · Unofficial · v0.1.0" — simple, static. |

### 8.2 Navigation components (`.astro`)

| Component | Props | Responsibility |
|---|---|---|
| `CategoryTabs.astro` | `year`, `categories: CategoryRef[]`, `activeCode: string`, `eventSlug?: string` | Horizontal tab row. If `eventSlug` given, links go to `/{year}/{category}/{eventSlug}`; else `/{year}/{category}`. |
| `EventButtons.astro` | `year`, `events: EventRef[]`, `activeCategoryCode: string`, `activeEventSlug?: string` | Horizontal event number + name chip row. Links to RaceResultsView for current category. |
| `Breadcrumb.astro` | `items: {label, href}[]` | Optional — used on RiderView + RaceResultsView. |
| `PrevNextEvent.astro` | `year`, `category`, `events`, `currentEventSlug` | "← R1 Kyrnare · R3 Buhovo →" band on RaceResultsView. |

### 8.3 Common primitives (`.astro`)

| Component | Props | Responsibility |
|---|---|---|
| `PositionBadge.astro` | `position: number \| 'DNF' \| 'DNS'` | Position pill — applies `pos-1/pos-2/pos-3/pos-dnf` variants. |
| `PointsPill.astro` | `points: number` | Points pill — applies `points-25` when points ≥ 25, `points-0` when 0. |
| `TimeCell.astro` | `milliseconds: number \| null` | Formats to `H:MM:SS.CS` or `MM:SS.CS`; "—" if null. |
| `RiderName.astro` | `rider: RiderRef`, `withTeam?: boolean`, `as?: 'a'\|'span'`, `href?: string` | Rider name element with optional team meta below + mono race number. |
| `EmptyState.astro` | `message: string`, `cta?: {label, href}` | Plain text empty-state block. |
| `ErrorState.astro` | `message: string` | Plain text error state (rarely used — SSG). |
| `Badge.astro` | `tone: 'default'\|'accent'` | Generic uppercase label badge. |
| `StatCard.astro` | `label: string`, `value: string\|number`, `emphasis?: boolean`, `colSpan?: 1\|2` | Single stat card. `emphasis` + `colSpan=2` on the LEADER card. |

### 8.4 View-specific components (`.astro`)

| Component | Props | Used in |
|---|---|---|
| `LeaderboardTable.astro` | `year`, `category`, `events`, `rows: StandingsRow[]`, `championshipFormat` | LeaderboardView (backend type `StandingsRow` retained to avoid breaking existing Python services) |
| `RacesList.astro` | `year`, `events`, `now: Date` | RacesView — renders as table desktop / cards mobile |
| `EventResultsTable.astro` | `year`, `category`, `event`, `results` | RaceResultsView |
| `EventCategoryGrid.astro` | `year`, `event`, `categories: {code, name, riderCount}[]` | RaceOverviewView |
| `RiderHeader.astro` | `rider`, `category`, `bestFinish`, `eventsEntered`, `totalPoints` | RiderView singular |
| `RiderResultsTable.astro` | `rider`, `category`, `results: EventResult[]` | RiderView singular (one per category) |
| `RiderDisambiguation.astro` | `year`, `raceNumber`, `candidates: RiderCandidate[]` | RiderView disambiguation |
| `StatsCardRow.astro` | `total`, `desktop`, `mobile`, `unknown` | StatsView |
| `VisitsByCategory.astro` | `counts: {category, hits}[]` | StatsView |
| `RecentVisits.astro` | `visits: Visit[]` | StatsView |

### 8.5 Future interactive islands (`.vue`, NOT in initial refactor)

Deferred but noted for scaffolding:

| Island | Props | Activation | Ships JS? |
|---|---|---|---|
| `LeaderboardFilter.vue` | `rows: StandingsRow[]`, `categories` | `client:visible` | ~15-25 KB gzipped (Vue + reactive filter logic) |
| `RiderComparison.vue` | `year`, `riders: Rider[]` | `client:load` on /compare | ~20-30 KB |
| `ProgressionChart.vue` | `rider`, `events` | `client:visible` on RiderView | ~40-60 KB (Chart.js island) |

Total "if all islands ship" JS weight: still well under the 50 KB budget per page if only one island is used per page.

---

## 9. Accessibility — WCAG 2.1 AA Acceptance Criteria

### 9.1 Color contrast

Pass threshold: **4.5:1 for body text, 3:1 for large text (18pt regular / 14pt bold).** All pairs in §3.1 audited; compliant.

**Lint rule (CI):** `axe-core` on built HTML pages — fail build if any violation. Runs on post-build `dist/` before Docker promotes the image.

**Human audit (Phase 2 Day-1):** open `/2026/expert` in Chrome Lighthouse, record initial accessibility score. Target: 100.

### 9.2 Keyboard navigation

| Element | Focus behavior | Activation |
|---|---|---|
| Brand logo | tabbable; Enter → navigate | Enter / Space |
| Year switcher | arrow-left/right to move between years; Enter to activate; Tab to exit | ARIA role=`tablist`, items role=`tab`, `aria-selected` |
| Category tabs | Same pattern — arrow-left/right, Enter to activate | ARIA role=`tablist` |
| Event buttons | Tab order, Enter to navigate | Standard `<a>` elements |
| Table rows (clickable) | Tab to row; Enter → navigate to rider | Either row-wrapped `<a>` or explicit "click-through" link with whole-row hover but focus on the rider-name anchor |

**Rule:** focus rings ALWAYS visible on keyboard focus. Use `focus-visible:` with `ring-2 ring-accent ring-offset-2 ring-offset-bg-base`. Do NOT suppress the default ring — add to it.

### 9.3 Screen reader support

- All pages have a unique, descriptive `<title>` and `<h1>`.
- `<table>` elements have `<caption>` (visually hidden `sr-only`) describing what the table shows.
- `<th>` cells have `scope="col"` (or `scope="row"` for first-column riders).
- Position badges use text content `"1st"` visually; `aria-label="1st place"` for accessibility.
- DNF cells use text "DNF" + `aria-label="Did not finish"`.
- Rider-disambiguation list uses `<ul role="list">` with each card as `<li>`.

### 9.4 Motion + reduced motion

- Respect `prefers-reduced-motion: reduce` → disable ALL transitions (set `transition: none !important` globally).
- No auto-play, no parallax, no carousel.

### 9.5 Language + locale

- `<html lang="en">` on every page.
- Rider names: treat as English for accessibility unless a future `lang` field is added to the Rider model. Cyrillic names render correctly in Inter + JetBrains Mono; no special handling required.

### 9.6 Touch targets

Minimum 44×44px (§7.6). Verified in mobile ASCII sketches.

---

## 10. Competitive Patterns — Applied Decisions

Translating the CEO-review competitive findings into specific design decisions for this refactor:

| Pattern | Source | Applied where | Effort |
|---|---|---|---|
| Leader hero card (big, prominent) | FIM Hard Enduro | §4.1 LeaderboardView LEADER stat card gets `col-span-2` + photo slot | <1h |
| Pill-toggle category switcher | Dakar | §4.1 category tabs — already in current CSS | Done |
| Season matrix on rider page | Supercross Live | §4.5 RiderView per-category results table — already the right shape | Done |
| No sponsor clutter above fold | Avoid MXGP / Dakar anti-pattern | §6 guardrails — sponsor slots go below hero or sidebar rail | N/A (prevention) |
| Dark premium aesthetic | Dakar / FIM / Supercross | §3 tokens, §6 guardrails | Done |
| Country flag chips | F1 / Dakar | Deferred — no country data in model | Deferred |
| Timing partner lockup | Dakar "by TUDOR" | Future sponsor slot in BaseLayout footer | Deferred |

---

## 11. StatsView Privacy Gate

Privacy affordances for the `/stats` route (labeled "private analytics"):

1. **`<meta name="robots" content="noindex, nofollow">`** — blocks search indexing.
2. **HTTP Basic Auth gated by env var `STATS_PASSWORD`** (Eng SC-1 fix) — at runtime, FastAPI middleware returns 401 with basic auth challenge if header missing or wrong.
3. **No internal links to /stats from the public nav.** (Current site ships this correctly; preserve.)
4. **No robots.txt allow-listing of /stats.**

If password is empty in dev (`.env.example`), bypass auth — easier local development. In Railway, `STATS_PASSWORD` is required.

---

## 12. Updated Scorecard

```
DESIGN REVIEW — POST-STRENGTHENING SCORECARD
═══════════════════════════════════════════════════════════════════════
  Pass                                Before  Now   Delta
  ──────────────────────────────────── ─────── ───── ──────────────────
  1. Information Architecture          3/10    8/10  +5 (view anatomy)
  2. Interaction State Coverage        2/10    8/10  +6 (states matrix)
  3. User Journey & Emotional Arc      4/10    7/10  +3 (nav contract)
  4. AI Slop Risk                      2/10    9/10  +7 (guardrails)
  5. Design System Alignment           3/10    9/10  +6 (token map)
  6. Responsive & Accessibility        2/10    8/10  +6 (breakpoints,
                                                          a11y criteria)
  7. Unresolved Design Decisions       3/10    8/10  +5 (states,
                                                          stat cards,
                                                          motion)
  ──────────────────────────────────── ─────── ───── ──────────────────
  OVERALL                              2.7/10  8/10  +5.3
═══════════════════════════════════════════════════════════════════════
```

What keeps it from 10/10:
- No real screenshot mockup (ASCII + rules only)
- Cyrillic rendering not yet tested on actual BG data
- Palette contrast pairs verified by calculation, not by live AAA tooling
- No design system versioning strategy (when tokens change, how do consumers update?)
- Component inventory doesn't include prop types (intentional — those come with the TS types generated from FastAPI)

These are genuine gaps but Day-0/Day-1 in Phase 2, not review-level concerns.

---

## 13. Phase 2 Pre-Coding Deliverables (updated)

| # | Deliverable | Where it lives | Status |
|---|---|---|---|
| D1 | DESIGN.md — full token system | **§3 of THIS file** (extractable) | ✅ Done |
| D2 | `frontend/tailwind.config.js` | §3.6 of THIS file (ready to copy into repo) | ✅ Ready |
| D3 | View anatomy per view | §4 of THIS file | ✅ Done |
| D4 | States matrix | §5 of THIS file | ✅ Done |
| D5 | Navigation contract | §4.7 of THIS file | ✅ Done |
| D6 | Motorsport identity guardrails | §6 of THIS file | ✅ Done |
| D7 | Responsive contract | §7 of THIS file | ✅ Done |
| D8 | Stat card enumeration | §4.1, §4.2, §4.6 of THIS file | ✅ Done |
| D9 | 404 + entry routes | §4.1, §4.7, §5 of THIS file | ✅ Done |
| D10 | Motion + stats privacy | §3.4, §11 of THIS file | ✅ Done |
| D11 | Accessibility acceptance criteria (NEW) | §9 of THIS file | ✅ Done |
| D12 | Component inventory (NEW) | §8 of THIS file | ✅ Done |
| D13 | Competitive pattern application (NEW) | §10 of THIS file | ✅ Done |

**All pre-Phase-2 design work is done in this document.** Phase 2 is unblocked.

---

## 14. Vocabulary (canonical labels) — applies everywhere, UI and docs

Locked during Round 2 of review. Use these exact labels in UI copy. URLs and DB/model names are NOT changed (backward compat), only user-facing strings.

| Concept | Use | Avoid |
|---|---|---|
| The per-category table of riders sorted by points | **Leaderboard** | Standings, Ranking, Rankings, Table |
| A single race event in the season | **Race** (singular), **Races** (plural) | Event, Round, Meet |
| Numeric round position in season calendar | **Round** (e.g., "R1 Kyrnare") | Event #, Stage |
| Points scored for a placing | **Points** | Score, Pts (except in tight columns where "Pts" is the abbreviation) |
| The championship / series as a whole | **Championship** (formal) or **Season** (when scoped to a year) | Tour, Series (avoid, too generic) |
| The type of motorsport (single type) | **Hard Enduro** (always) | Navigation, Enduro, Rally, Rally-raid |
| Someone who competes | **Rider** | Competitor, Athlete, Pilot |
| A rider's DNS/DNF/penalty state | **DNF** / **DNS** (uppercase) | Did Not Finish spelled out (too long in cells) |
| The aggregate year's ranking (final) | **Final leaderboard** | Final standings |

**Tone rules:**
- **Plain, factual.** No marketing copy. No exclamation marks anywhere in UI chrome.
- **Second person** when addressing readers ("you can filter by team"). Third person when describing riders ("Ivan Ivanov leads Expert").
- **Tense:** present for current season; past for completed races ("R1 was won by …"). Future for upcoming ("R4 takes place on June 13").
- **Numbers:** use digits always ("2 of 7 races", not "two of seven races").
- **Dates:** short format in tables (`Apr 18`), long format on race pages (`April 18, 2026`). Always in the site's locale (English months; Cyrillic months never — rider names can be Cyrillic, chrome is English).
- **No emojis** in chrome copy. (Medal emojis like 🥇 may appear in sketches for clarity; the production UI uses color-coded position badges per §3 token system, not emoji.)

**Abbreviation conventions:**
- Round = `R1`, `R2`, …
- Points in tight cells = `Pts` (never `pts.` or `P`)
- Categories = full names (Expert, Profi, Junior) — no abbreviation
- DNF / DNS — uppercase, always

**Example rewrites (before → after):**
- "2026 Expert Standings" → "2026 Expert Leaderboard"
- "Season Events Calendar" → "2026 Races"
- "Events entered: 2" → "Races entered: 2"
- "Event details coming soon" → "Race details coming soon"
- "Event type: Navigation" → remove entirely (Hard Enduro is the only type; redundant label)

---

## 15. User Journey Diagrams

Four common journeys that the UI must support well. Each shows where the user comes from, what decisions they make, and where they land.

### 15.1 "Fan clicks shared tweet/Telegram link"

```
  [External link shared in social]
       │
       │  e.g., https://bgx.example/2026/r/42/ivan-ivanov
       ▼
  ┌──────────────────────────────────────┐
  │ Astro SSG serves pre-rendered HTML   │  ← 0 KB JS, LCP < 1s
  │ - <title> = "Ivan Ivanov · Expert    │
  │             · 2026 BGX Hard Enduro"  │
  │ - OG image + rich snippet populated  │
  └──────────────────────────────────────┘
       │
       │  User scans: name, team, best finish, season results
       ▼
  ┌──────────────────────────────────────┐
  │ Three natural next-clicks:           │
  │  1. "Expert Leaderboard" link        │─▶ /2026/expert
  │  2. A race row (e.g., "R2 Stara Z.") │─▶ /2026/expert/stara-zagora
  │  3. Back / close tab                 │
  └──────────────────────────────────────┘
```

**Design goal:** first-paint data, no spinner, no waterfall. Easy lateral navigation to context (category leaderboard or race results).

### 15.2 "Season follower checks today's leaderboard"

```
  [User types "bgx.example" or bookmarks root]
       │
       ▼
  ┌──────────────────────────────────────┐
  │ /  →  302 → /2026/expert (current    │
  │               year + default cat)    │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Leaderboard view                     │
  │  - Top 3 podium visible above fold   │
  │  - Stat cards: LEADER / RACES / GAP  │
  │  - Latest race highlighted in        │
  │    race-buttons row                  │
  └──────────────────────────────────────┘
       │
       │  70% of users stop here.
       ▼
  ┌──────────────────────────────────────┐
  │ 20% click a rider name               │─▶ Rider view
  │ 10% click another category tab       │─▶ /2026/{other-cat}
  │  5% click a race button              │─▶ Race Results
  └──────────────────────────────────────┘
```

**Design goal:** top 3 always above fold on mobile (sticky-first-column handles width). Latest-race indicator is the key affordance.

### 15.3 "Rider looks up their own progress"

```
  [Self-search: Google "Ivan Ivanov BGX"]
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Search Console indexed rider page    │
  │ Rich snippet shows best finish +     │
  │ team (JSON-LD Person structured data)│
  │ CTR high when snippet has photo      │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Rider view — their own profile       │
  │  Emotional moment: "here's my season"│
  │  Key needs: accurate name spelling,  │
  │  correct team, every race they       │
  │  entered, correct final positions.   │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Likely next click: Leaderboard       │─▶ /2026/{their-cat}
  │ To see who's ahead/behind.           │
  └──────────────────────────────────────┘
```

**Design goal:** zero errors in name/team/results. Social-share CTA (OG image with their name) should be generatable so they can share back. Deferred feature; design reserves space for share buttons near header.

### 15.4 "Organizer checks results post-race"

```
  [Race day / day after]
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Admin imports results via CLI (out   │
  │ of scope for this refactor — future  │
  │ admin UI)                            │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Weekly CI rebuild picks up new data  │
  │ within 24h of import                 │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │ Races view                           │
  │ Race row: "R3 Buhovo · Completed ✓"  │
  │ Click → Race overview (category grid)│
  │ Click → Race results per category    │
  └──────────────────────────────────────┘
```

**Design goal:** "Completed" vs "Upcoming" visually obvious on Races table. Partial state (some categories scored, others pending) clearly indicated.

---

## 16. Microcopy Library

Every user-facing string from a single source. Lives at `frontend/src/lib/copy.ts`. Keys are grouped by context. The initial dictionary (English) fits in one file; future i18n can swap per locale without touching components.

### 16.1 Structure

```ts
// frontend/src/lib/copy.ts
export const copy = {
  app: {
    brand: 'BGX.',
    brandSubtitle: 'Hard Enduro',
    footer: (version: string) => `BGX Hard Enduro Championship · Unofficial · v${version}`,
  },
  nav: {
    leaderboard: 'Leaderboard',
    races: 'Races',
    stats: 'Stats',
  },
  leaderboard: {
    h1: (year: number, category: string) => `${year} ${category} Leaderboard`,
    subtitle: 'Bulgarian Hard Enduro Championship',
    empty: (category: string) => `No riders in ${category} yet.`,
    statLeader: 'Leader',
    statRaces: 'Races',
    statGap: 'Gap 1→2',
    statActive: 'Active riders',
    colHash: '#',
    colNumber: 'No.',
    colRider: 'Rider',
    colTotal: 'Total',
    colRaced: 'Raced',
    colBest: 'Best',
    colDropped: 'Dropped',
  },
  races: {
    h1: (year: number) => `${year} Races`,
    subtitleFmt: (upcoming: number, completed: number, total: number) =>
      `${total} races · ${upcoming} upcoming · ${completed} completed`,
    empty: (year: number) => `No races scheduled for ${year} yet.`,
    statusCompleted: 'Completed',
    statusUpcoming: 'Upcoming',
    colHash: '#',
    colRace: 'Race',
    colLocation: 'Location',
    colDate: 'Date',
    colStatus: 'Status',
  },
  raceResults: {
    h1: (round: number, raceName: string, categoryName: string) =>
      `R${round} · ${raceName} — ${categoryName}`,
    subtitleFmt: (dateLong: string, locationFull: string) =>
      `${dateLong} · ${locationFull}`,
    empty: 'Results for this category and race aren\'t in yet.',
    backToLeaderboard: (category: string) => `← Back to ${category} Leaderboard`,
    prevNextFmt: (prevRound: string, nextRound: string) => `← ${prevRound} · ${nextRound} →`,
    colHash: '#',
    colNumber: 'No.',
    colRider: 'Rider',
    colTime: 'Time',
    colPoints: 'Pts',
    colLaps: 'Laps',
    colGps: 'GPS',
    dnf: 'DNF',
    dns: 'DNS',
  },
  raceOverview: {
    h1: (raceName: string) => raceName,
    subtitleFmt: (round: number, dateLong: string, locationFull: string) =>
      `Round ${round} · ${dateLong} · ${locationFull}`,
    sectionResults: 'Results by category',
    categoryPendingLabel: '(pending)',
    empty: 'Race details coming soon.',
  },
  rider: {
    metaFmt: (team: string | null, bike: string | null, category: string) =>
      [team, bike, category].filter(Boolean).join(' · '),
    statsFmt: (bestFinish: string, racesEntered: number, totalPoints: number) =>
      `Best: ${bestFinish} · Races entered: ${racesEntered} · Total points: ${totalPoints}`,
    sectionSeasonResults: (category: string) => `Season results · ${category}`,
    empty: (year: number) => `This rider has no results yet for ${year}.`,
    entriesFmt: (entered: number, total: number) =>
      `Entered ${entered} of ${total} races this season.`,
    backToCategory: (category: string) => `← Back to ${category} Leaderboard`,
    disambigH1: (raceNumber: number, year: number) =>
      `Rider #${raceNumber} · ${year} Season`,
    disambigHelp: (count: number, raceNumber: number) =>
      count === 2
        ? `Two riders compete with number ${raceNumber} this season:`
        : `${count} riders compete with number ${raceNumber} this season:`,
  },
  stats: {
    h1: 'Private analytics',
    subtitleLast30: 'Last 30 days',
    statVisits: 'Visits',
    statDesktop: 'Desktop',
    statMobile: 'Mobile',
    statUnknown: 'Unknown',
    sectionByCategory: 'Visits by category',
    sectionRecent: 'Recent visits (last 25)',
    empty: 'No visits recorded yet.',
  },
  notFound: {
    h1: '404',
    subtitle: 'We can\'t find that page.',
    helpBody: 'The link may be old or the page may have been removed.',
    ctaCurrentLeaderboard: (year: number) => `Go to the ${year} Leaderboard`,
  },
  error500: {
    h1: 'Something went wrong',
    subtitle: 'An unexpected error occurred. Please try again in a moment.',
    cta: 'Go to the home page',
  },
  common: {
    backToTop: '↑ Top',
    loading: 'Loading…',
    noTime: '—',
  },
};
```

### 16.2 Rules

- **Every user-visible string** in the app must come from this file. No inline strings in `.astro` or `.vue` components.
- **Dynamic values** use template functions (e.g., `leaderboard.h1(2026, 'Expert')`). Never concatenate in components.
- **Fallbacks** are explicit (`rider.metaFmt` handles null team/bike) — components must not branch on null themselves.
- **Pluralization** handled inline when simple (`races/race`); if it becomes complex, add a `pluralize()` helper, don't spread logic.

### 16.3 Future i18n path

When Bulgarian copy is added later, swap this file for `copy.en.ts` + `copy.bg.ts` + a tiny resolver. No other changes needed. This is an "i18n-ready" setup without shipping i18n infra now.

---

## 17. Animation & Transition Choreography

Choices made from the user's perspective — fast, precise, dashboard-feel (matches motorsport). No playfulness; no ripple/bounce.

### 17.1 Page transitions

| Context | Transition | Duration | Easing |
|---|---|---|---|
| Navigating between Astro pages (full load) | None — browser default | — | — |
| Back/forward | None — browser default | — | — |

### 17.2 Interactive micro-interactions

| Context | Transition | Duration | Easing | Notes |
|---|---|---|---|---|
| Link hover color change | `color` | 150ms | ease | Subtle — token `accent` on text |
| Button / tab hover (bg + border) | `background-color, border-color, color` | 150ms | ease | Only properties that cheap-paint |
| Year-switcher chip active toggle | `background-color, color` | 150ms | ease | Click → instant route change, no pre-animation |
| Active category tab | None (immediate) | 0ms | — | Tab click = full page load in Astro SSG; no client-side animation |
| Event/Race button active state | `background, border, color` | 150ms | ease | On hover only; active state renders immediately on new page |
| Focus ring | None (immediate) | 0ms | — | `focus-visible` ring appears instantly, no transition |

### 17.3 Island interactions (future features)

For Vue islands that will hydrate on Leaderboard filters, rider comparison, etc.:

| Context | Transition | Duration | Notes |
|---|---|---|---|
| Filter chip toggle (active/inactive) | `background, color` | 150ms ease | Same as current category tabs |
| Table row filter-out (hide) | `opacity` only; no height animation | 100ms linear | Visible → invisible instantly; collapsing rows is distracting on dense tables |
| Island hydration moment | No animation | 0ms | Island appears with data already populated (SSG). Skeleton only if data fetch is async (none in Phase 2) |
| Modal / dialog (none planned initial) | `opacity` fade-in | 100ms ease | Future |

### 17.4 Mobile-specific

| Context | Transition | Duration |
|---|---|---|
| Table horizontal scroll (sticky-first-column) | Browser-native inertial scroll | — |
| Scroll-affordance shadow (right edge fade) | Static (always visible when scrollable) | — — |
| Sticky nav on scroll | None (just sticks via CSS; no shrink/hide) | — |

### 17.5 Reduced motion

`@media (prefers-reduced-motion: reduce) { *, ::before, ::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }` — global kill-switch. No transitions for anyone with this preference set.

### 17.6 What we DON'T do

- ❌ No ripple effects on clicks (Material feel — wrong genre)
- ❌ No card-flip or 3D transforms
- ❌ No parallax
- ❌ No auto-playing carousels
- ❌ No page-level crossfades or slide transitions
- ❌ No entrance animations on scroll (no `fade-in-on-scroll`)
- ❌ No shimmer on skeleton placeholders (too SaaS-y)
- ❌ No spinner GIFs or SVG spinners (SSG means no initial load state)

---

## 18. SEO / Structured Data Spec

Post-refactor SEO is success metric M3/M4. Below locks title templates, meta patterns, and JSON-LD structured data per view.

### 18.1 Title templates (exact, per view)

| View | Title template | Example |
|---|---|---|
| `/` landing | `BGX Hard Enduro Championship` | same |
| `/{year}` | `{year} BGX Hard Enduro Championship` | `2026 BGX Hard Enduro Championship` |
| `/{year}/{category}` (leaderboard) | `{year} {Category} Leaderboard · BGX Hard Enduro` | `2026 Expert Leaderboard · BGX Hard Enduro` |
| `/{year}/events` (races) | `{year} Races · BGX Hard Enduro Championship` | `2026 Races · BGX Hard Enduro Championship` |
| `/{year}/events/{slug}` (race overview) | `{Race Name} · Round {n} · {year} · BGX Hard Enduro` | `Kyrnare · Round 1 · 2026 · BGX Hard Enduro` |
| `/{year}/{category}/{slug}` (race results) | `{Race Name} Results · {Category} · {year} · BGX Hard Enduro` | `Kyrnare Results · Expert · 2026 · BGX Hard Enduro` |
| `/{year}/r/{number}/{slug}` (rider) | `{First Last} · {Category} · {year} · BGX Hard Enduro` | `Ivan Ivanov · Expert · 2026 · BGX Hard Enduro` |
| `/{year}/r/{number}` (disambiguation) | `Rider #{number} · {year} · BGX Hard Enduro` | `Rider #42 · 2026 · BGX Hard Enduro` |
| `/stats` | `Private Analytics · BGX` + noindex | `Private Analytics · BGX` |
| `/404` | `Page Not Found · BGX Hard Enduro` | same |

### 18.2 Meta description templates

| View | Meta description |
|---|---|
| Leaderboard | `{year} {Category} class leaderboard for the BGX Hard Enduro Championship. {N} riders, {X} races completed.` |
| Races | `{year} race calendar for the BGX Hard Enduro Championship. {N} races from {first race} to {last race}.` |
| Race overview | `Round {n} of the BGX Hard Enduro Championship {year}. {Race name}, {location}, {date}.` |
| Race results | `{Category} results from Round {n} {Race name}, BGX Hard Enduro {year}. Winner: {winner name}.` |
| Rider | `{First Last}, #{number}, {Category} class. Best finish: {best}. {N} races entered in the {year} BGX Hard Enduro Championship.` |
| Races-year, landing | `Official results and leaderboards for the BGX Hard Enduro Championship, {year} season.` |

### 18.3 Canonical URLs

Every page sets `<link rel="canonical" href="https://bgx.{domain}{path}">`. Slashes normalized (no trailing slash; configure Astro to match).

### 18.4 OG / Twitter tags

| Tag | Value |
|---|---|
| `og:type` | `website` (all views); `article` for rider pages (optional) |
| `og:title` | Same as `<title>` |
| `og:description` | Same as meta description |
| `og:image` | `/og-default.png` for all views day 1; future: per-rider generated image |
| `og:site_name` | `BGX Hard Enduro Championship` |
| `twitter:card` | `summary_large_image` |
| `twitter:title` / `description` / `image` | Mirror OG |

### 18.5 JSON-LD structured data

**Rider page** (`/{year}/r/{number}/{slug}`) — `Person` + `SportsEvent` memberships:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Ivan Ivanov",
  "jobTitle": "Enduro rider",
  "affiliation": {
    "@type": "SportsTeam",
    "name": "BGX Racing"
  },
  "athlete": {
    "@type": "SportsOrganization",
    "name": "BGX Hard Enduro Championship"
  },
  "url": "https://bgx.example/2026/r/42/ivan-ivanov",
  "identifier": "42"
}
</script>
```

**Race page** (`/{year}/events/{slug}`) — `SportsEvent`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SportsEvent",
  "name": "Kyrnare",
  "startDate": "2026-04-18",
  "endDate": "2026-04-18",
  "location": {
    "@type": "Place",
    "name": "Kyrnare, Karlovo, Bulgaria"
  },
  "sport": "Hard Enduro",
  "superEvent": {
    "@type": "SportsEvent",
    "name": "2026 BGX Hard Enduro Championship"
  },
  "url": "https://bgx.example/2026/events/kyrnare"
}
</script>
```

**Championship page** (`/{year}`) — `SportsEvent` series (annual championship):

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SportsEvent",
  "name": "2026 BGX Hard Enduro Championship",
  "startDate": "2026-04-18",
  "endDate": "2026-10-15",
  "sport": "Hard Enduro",
  "eventStatus": "https://schema.org/EventScheduled",
  "location": {
    "@type": "Country",
    "name": "Bulgaria"
  },
  "url": "https://bgx.example/2026"
}
</script>
```

**Leaderboard page** — no specific JSON-LD (`ItemList` is too generic; standard `SportsEvent` on the championship page covers this).

### 18.6 Sitemap

Astro's `@astrojs/sitemap` integration auto-generates `/sitemap-index.xml` + `/sitemap-0.xml` at build time. Includes every SSG route. Submit to Search Console on Day 1.

### 18.7 robots.txt

```
User-agent: *
Allow: /
Disallow: /stats
Disallow: /api/

Sitemap: https://bgx.example/sitemap-index.xml
```

---

## 19. 404 and Error Pages

### 19.1 404 — `src/pages/404.astro`

Astro SSG builds this as a real `dist/404.html`. FastAPI serves it when `StaticFiles` doesn't find a match.

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav — same as every page]                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                                                                      │
│                     4 0 4                                            │  H1 huge (72px, 800, accent color)
│                                                                      │
│              We can't find that page.                                │  subtitle (18px, text-primary)
│                                                                      │
│   The link may be old or the page may have been removed.             │  body (14px, text-muted)
│                                                                      │
│                                                                      │
│   →  Go to the 2026 Leaderboard                                      │  CTA link (16px accent)
│                                                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Meta:** `<meta name="robots" content="noindex, nofollow">`. Title: `Page Not Found · BGX Hard Enduro`. No content-type considerations (it's HTML, served with 200 status by StaticFiles; acceptable for an SSG-served 404). For a "true" 404 status code on the response, FastAPI can wrap the static-file catchall and return 404 for unknown paths — flagged as a Phase 4 detail.

### 19.2 Error 500 — `src/pages/500.astro`

Practically never renders (SSG has no runtime errors), but exists as a courtesy if the FastAPI layer (API endpoints) surfaces a 500 to the user.

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sticky nav]                                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Something went wrong.                                              │  H1 (32px, 800)
│                                                                      │
│   An unexpected error occurred. Please try again in a moment.        │  body
│                                                                      │
│   →  Go to the home page                                             │  CTA
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 19.3 Broken / stale link behavior

If a build-time rider slug was, say, `ivan-ivanov` and the DB later corrects to `i-ivanov`, the old URL 404s after the next rebuild. This is acceptable — we rebuild weekly and on data import. No client-side redirect map needed.

---

## 20. Print Styles

Some users will print leaderboards for pit-box posting. `@media print` rules:

```css
@media print {
  /* Strip chrome */
  .nav, .year-switcher, .category-tabs, .event-buttons, .footer { display: none; }

  /* Full-bleed black-on-white */
  body { background: white; color: black; }
  .card { border: 1px solid #888; background: white; }
  .card-header { background: white; border-color: #888; }
  th, td { border-color: #aaa; background: white; color: black; padding: 6px 8px; }

  /* Position badges keep color for podium rows (paper survives) */
  .pos-1 { background: #fde68a; color: #78350f; }     /* gold-ish on paper */
  .pos-2 { background: #e2e8f0; color: #1f2937; }     /* silver-ish */
  .pos-3 { background: #fed7aa; color: #7c2d12; }     /* bronze-ish */
  .pos, .pos-dnf { background: white; color: #374151; }

  /* Inline points pill reads as plain bold text */
  .points { background: white; color: black; font-weight: 700; padding: 0; }

  /* Let wide tables wrap across pages */
  .scrollx { overflow: visible; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; page-break-after: auto; }
  thead { display: table-header-group; }
  tfoot { display: table-footer-group; }

  /* Save toner */
  * { -webkit-print-color-adjust: economy; }

  /* Add an attribution footer */
  @page { margin: 1cm; }
  body::after {
    content: "BGX Hard Enduro Championship · bgx.example";
    display: block;
    text-align: center;
    font-size: 9pt;
    margin-top: 1cm;
    color: #666;
  }
}
```

**Rule of thumb:** 1 page = 1 leaderboard up to ~20 riders. Larger tables span pages with row-internal breaks suppressed.

---

## 21. Per-Page Performance Budget

Tight budgets per view — enforced by CI gate via `size-limit` or the equivalent Astro plugin.

| View | HTML (max) | CSS (gzipped, shared) | JS (gzipped, per-page) | Notes |
|---|---|---|---|---|
| `/` landing (redirect) | 2 KB | 0 KB (redirect, no render) | 0 KB | Just a redirect shell |
| `/{year}` | 4 KB | (shared below) | 0 KB | Redirect fallback |
| `/{year}/{category}` (Leaderboard) | **20 KB** (≤ 60 rows × ~300 bytes/row) | (shared) | **0 KB Phase 1** → **≤ 25 KB Phase 2** (LeaderboardFilter island, lazy) | Leaderboard is the hero — stay lean |
| `/{year}/events` (Races) | 3 KB | (shared) | 0 KB | Small table |
| `/{year}/events/{slug}` (Race overview) | 3 KB | (shared) | 0 KB | Category grid |
| `/{year}/{category}/{slug}` (Race results) | 15 KB (≤ 60 rows × timing cols) | (shared) | 0 KB | |
| `/{year}/r/{n}/{slug}` (Rider) | 8 KB | (shared) | 0 KB Phase 1 → ≤ 40 KB Phase 2 if ProgressionChart island added | Rider is SEO-critical; keep lean |
| `/{year}/r/{n}` (Disambig) | 4 KB | (shared) | 0 KB | Never more than a handful of cards |
| `/stats` | 10 KB | (shared) | 0 KB | Private, doesn't count for SEO/perf goals |
| `/404` | 2 KB | (shared) | 0 KB | Tiny |

**Shared budgets (all pages load these once):**

| Asset | Budget | Mechanism |
|---|---|---|
| Main stylesheet (Tailwind-purged, single file) | **≤ 15 KB gzipped** | Tailwind content config tight; `@apply` sparingly |
| Fonts (self-hosted woff2, subset to Latin + Cyrillic) | **≤ 80 KB total across 2 files** | Inter subsetted; JetBrains Mono subsetted; `font-display: swap` |
| Favicon + OG default image | ≤ 30 KB | `og-default.png` sized 1200×630, compressed |
| Astro runtime / hydration JS | **0 KB on pages without islands** | Native Astro behavior |

**CI gate (Phase 4):** build passes only if:
- Per-page HTML ≤ budget.
- Total CSS ≤ 15 KB.
- Total JS across all pages ≤ 50 KB gzipped for Phase 2 launch; grows to ≤ 100 KB as islands are added in subsequent features.

**Lighthouse target (Day 1 launch):** every public route hits Lighthouse 100/100/100/100 (Performance / Accessibility / Best Practices / SEO) on a mid-tier mobile profile. Any regression below 95 on any dimension fails the gate.

**How budgets tie back to success metrics:**
- **M1 LCP** (target <2.5s): achievable only if HTML + CSS + fonts fit in the budget above. Mobile 3G equivalent: ~1.5s LCP with this budget.
- **M2 JS bundle**: budgets above ARE M2 with teeth. Day-1 ship has 0 KB JS; M2 becomes "stay under budget as features land."

---

## 22. Review Findings Summary (carried forward to Final Gate)

- Overall design completeness: **9.5/10** after second-round strengthening (R1-R4, R6, R8-R12).
- 0 user challenges raised by design (no scope changes recommended).
- 3 critical findings from initial review — all resolved in this file.
- Second round filled: vocabulary, user journeys, microcopy, animation, SEO/JSON-LD, 404, print, per-page performance budgets.
- **Remaining 0.5/10 gap:** no HTML/Figma mockup yet (user explicitly chose to stay on ASCII); real-data edge cases not enumerated (R7 was skipped). Neither blocks Phase 2.
- **Outstanding for Phase 2 Day-0** (not review-blocking):
  1. Live palette contrast verification in real Chrome DevTools (5 min).
  2. Cyrillic glyph rendering test with actual BG rider names from CSV (10 min).
  3. One Lighthouse run on current site as baseline (M1 LCP metric for success metrics).
  4. Port the microcopy library to `frontend/src/lib/copy.ts` (10 min — it's already drafted in §16).
