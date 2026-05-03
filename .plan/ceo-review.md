# CEO Review — Refactor Plan (FastHTML → FastAPI + Vue 3)

> Review of `.plan/refactor-plan.md`. Run as Phase 1 of `/autoplan` on branch `refactor/fastapi-vue`, commit `cd2118f`.
> **Mode:** SELECTIVE EXPANSION.
> **Voices:** Claude primary + Claude subagent. Codex CLI unavailable → single-voice mode `[subagent-only]`.

---

## 0A. Premise Challenge

Seven premises the plan rests on, with adversarial scrutiny:

| # | Premise | Stated? | Holds? | Notes |
|---|---|---|---|---|
| P1 | The refactor is necessary | Implied | ⚠️ Weak | "FastHTML couples rendering to Python and makes rich interactivity expensive" — but no rich interactivity is in the scope of this refactor. The plan replaces server-rendered HTML with client-rendered HTML that renders the same tables. What's the concrete user benefit now? |
| P2 | Vue 3 is the right frontend | Implicit | ⚠️ Not examined | Svelte, SolidJS, HTMX+Alpine never compared. HTMX-on-FastHTML is particularly relevant — it achieves most of the "future interactivity" wins without the rewrite. |
| P3 | Mosaic Lite fits | Stated | ⚠️ Cost underestimated | Mosaic Lite is a light-themed Tailwind admin template. Converting to dark + podium palette is design work, not a drop-in. Plan says "cherry-pick components" but doesn't scope the conversion. |
| P4 | Single Railway service | Decided | ✅ Sound | Right call for the scale. |
| P5 | Monorepo layout | Decided | ✅ Sound | Appropriate for solo/small team. |
| P6 | /app URL split is OK | Decided | ⚠️ Real SEO risk | Plan adds 6 redirects — good. But /app SPA pages aren't SEO-equivalent to the current HTML pages. |
| P7 | Read-only dashboard needs a SPA | Implicit | ⚠️ Biggest question | For a public informational site with no auth/state, SPA is net-negative on day one (SEO loss, cold-start cost) and net-positive only if future interactivity materializes. The plan doesn't commit to that interactivity. |

**Biggest premise risk: P7.** The business case depends on future features (filters, charts, live timing) that aren't in this refactor. If those features slip or get cut, we've traded a working, fast, crawler-friendly site for a bundled SPA that does the same thing with extra steps.

---

## 0B. Existing Code Leverage (What Already Exists)

| Sub-problem | Existing code | Reuse strategy |
|---|---|---|
| Standings calculation | `src/services/standings.py::get_standings` | Straight import, wrap in Pydantic schema |
| Rider profile | `src/services/rider.py::get_rider_profile` | Same |
| Rider disambiguation | `src/services/rider.py::riders_sharing_number` | Same |
| Domain models | `src/db/models.py` (Season, Category, Event, Rider, EventResult, Visit) | Straight reuse |
| DB session | `src/db/session.py` | Straight reuse |
| Constants | `src/seasons.py` (RACE_ORDER_2025, CATEGORIES_2025) | Straight reuse |
| Migrations | `alembic/versions/0001_initial_schema.py` | Straight reuse |
| CSV importers | `scripts/import_2025.py`, `import_event.py`, `seed_calendar.py` | Straight reuse |
| Visit tracking semantics | `src/database.py::track_visit` | Logic reused; implementation moves to middleware or POST /api/track |
| Golden test | `tests/test_standings_2025.py` | Straight reuse |
| Visual design tokens (dark + gold + podium) | `src/ui/styles.py` (~180 lines CSS, 8.6 KB) | Tokens port to Tailwind config; hand-rolled CSS gets replaced |

**High reuse**: services, models, migrations, importers — roughly 1000 lines of Python that don't need rewriting. The rewrite is concentrated in routes + UI + deployment glue.

---

## 0C. Dream State Mapping

```
CURRENT (April 2026):
  Server-rendered FastHTML pages. Postgres + Alembic. 11 routes.
  ~180 lines of polished dark CSS. Single Docker image on Railway.
  Zero JS. Fast first paint. Crawler-friendly. ~0 ops pages.

THIS PLAN (May 2026):
  FastAPI JSON API (/api/*). Vue 3 SPA (/app/*). Mosaic Lite dark.
  Same data. Same deploy target. Same UX surface area.
  Cost: ~1-2 weeks solo effort. SEO risk. Bundle size.

12-MONTH IDEAL (April 2027):
  Rider comparison tool.
  Filters (team, bike, age group) across standings.
  Live results during event days.
  Progression charts across events.
  Mobile-first responsive (current = responsive, not mobile-first).
  Admin UI for event result upload (replaces import scripts).
  Social share images per rider / event.
  Maybe race-day timing system integration.
  Push notifications for event day.
```

The plan gets us ~30% of the dream state — the platform for the rest. The other 70% is real work that would be dramatically cheaper with Vue than with FastHTML.

---

## 0C-bis. Implementation Alternatives (the plan's biggest gap)

The plan committed to Vue + Mosaic Lite without comparing to alternatives:

| # | Approach | Effort (CC) | Ceiling | Pros | Cons |
|---|---|---|---|---|---|
| A | **HTMX on FastHTML** (no rewrite) | 2-3 days | Medium | Ship filters/tabs/search in days, keep server-rendering + SEO, zero build step, zero new deps except HTMX script | UX ceiling lower than Vue; dev-familiarity lower (niche); long-term features (charts, comparison) harder |
| B | **FastAPI + Vue 3 + Mosaic Lite** (this plan) | 1-2 weeks | High | Modern stack, easy to add rich features, better dev ergonomics once in place, type safety via generated schemas | SEO risk without SSR; build pipeline overhead; Mosaic dark-theme adaptation cost; bundle size |
| C | **Nuxt 3 SSR + FastAPI** | 1.5-2.5 weeks | Highest | Vue ergonomics AND SSR (solves SEO); colocates API routes if desired | More complex deploy; Nuxt adds conceptual weight; Railway Nuxt setup less documented |
| D | **"Do nothing" — enhance current stack** | 0.5-1 day | Low | Zero risk, zero regression. Invest the week in content (more seasons, richer rider pages, social share images) | Doesn't unlock dream-state features |

**Plan choice is B.** Defensible but A deserves a serious look before committing the week. If the near-term goal is "same data, slightly nicer UI", A wins on effort. If the near-term goal is "platform for the 12-month dream state", B or C wins. Between B and C, C (Nuxt) wins on SEO — the plan's one-line dismissal is not evidence.

Surfacing as **USER CHALLENGE UC-1 / UC-2** at the final gate.

---

## 0D. Scope Decisions (SELECTIVE EXPANSION)

| # | Candidate | Blast radius | CC effort | Decision | Rationale |
|---|---|---|---|---|---|
| E1 | `@vueuse/head` per-route meta/OG tags | frontend/ | <2h | **Accept** — include in Phase 2 scaffold | Cheap SEO floor; any SPA should have this day-one. P1 (completeness). |
| E2 | `openapi-typescript` for API types | frontend/ + backend/ | <1h | **Accept** — add to Phase 1 ("firm commit", not "consider") | Prevents type drift; type-safe API client. P1. |
| E3 | Pre-render top N pages via `vite-plugin-prerender` | frontend/ | ~4h | **Accept** — add to Phase 4 (or replaced by Nuxt if UC-2 accepted) | Fixes SEO regression for the 10-20 most-linked pages. P1 completeness, P2 blast radius. |
| E4 | Rate limit middleware (slowapi or starlette-limiter) | backend/ | ~1h | **Accept** — Phase 1 | Cheap defense against scrape/accidental DoS. Public API needs it. |
| E5 | Structured logging (structlog) | backend/ | ~2h | **Defer** | Nice to have; not blocker. TODOS.md. |
| E6 | Admin UI replacing import scripts | frontend/ + backend/ | ~2 days | **Defer** | Out of blast radius. TODOS.md. |
| E7 | Rider comparison tool | frontend/ + backend/ | ~1 day | **Defer** | Out of blast radius, requires UX design first. TODOS.md. |
| E8 | Live results WebSocket | backend/ | ~3 days | **Defer** | Big scope, needs event-day infra. TODOS.md. |

**Expansions accepted: E1, E2, E3, E4.** Plan updates to fold these into the relevant phases.

---

## 0E. Temporal Interrogation

- **Hour 1** (Phase 0): `git mv` into backend/. Docker paths updated. App still boots. No user-visible change.
- **Hour 6** (Phase 1 mid): FastAPI skeleton exists, 3/11 endpoints ported, pytest partially green.
- **Day 1 end** (Phase 1 done): All 11 endpoints as JSON. Legacy redirects wired. pytest green. No frontend yet.
- **Day 2** (Phase 2): Vue scaffold boots. Sidebar/topbar visible in dark theme. Six route stubs.
- **Day 3-4** (Phase 3 a/b): Standings + Events views working. Rider view (critical — identity rule) wired.
- **Day 5-6** (Phase 3 c/d/e/f): EventResults, EventOverview, Stats views. Polish.
- **Day 7** (Phase 4): Multi-stage Docker. Railway preview green.
- **Day 8** (Phase 5): Smoke. Merge.
- **Day 8+1** (post-launch): Users hit old URLs → 302 → Vue load. Works.
- **Day 30** (regression check): SEO crawler index for rider pages — down? If pre-render (E3) is in, probably fine. Without it, measurable loss likely.

**Biggest drift risk:** Mosaic Lite dark-theme adaptation. If the palette override is fussy (contrast, component-by-component tuning), Phase 2 slips. Mitigate by time-boxing the palette work to 1 day, with a "fall back to raw Tailwind" escape hatch.

---

## 0F. Mode Confirmation

**SELECTIVE EXPANSION** confirmed:
- HOLD the stack choice (Vue + Mosaic Lite + single Railway service + monorepo + /app split) — pending USER CHALLENGES.
- EXPAND to include E1-E4 (`@vueuse/head`, openapi-typescript, pre-render, rate limit).
- DEFER E5-E8 to TODOS.md.

---

## Required Outputs

### NOT in scope (deferred to TODOS.md)

- Admin UI replacing import scripts
- Rider comparison tool
- Live results WebSocket
- i18n (en/bg)
- Structured logging
- SSR migration (evaluate post-launch; pre-render covers the floor — or Nuxt if UC-2 accepted)
- Bulgarian locale for CSV headers → UI

### Error & Rescue Registry

| Failure | Where | Detection | Rescue |
|---|---|---|---|
| Alembic migration fails on deploy | Docker CMD | Container health check fails | Rollback image; investigate; Railway has image history |
| `/api/seasons/{year}/standings/{cat}` 500 on missing category | backend | Pytest contract test + structured log | Return 404 with Pydantic error body |
| Vue bundle fails to build | Dockerfile Stage 1 | CI check / Docker build error | Block deploy; don't promote broken image |
| SPA fallback serves index.html for real 404 | backend static mount | E2E test: GET /app/nonexistent → 200+index.html expected for SPA, but API 404 must still be 404 | Order: mount /api/* router BEFORE catch-all |
| Visit tracking middleware spikes DB | backend | APM / Postgres slow log | Move to BackgroundTasks or POST /api/track + throttle |
| `/app/2026/expert` direct load cold-start slow | Railway | User perception, RUM | Pre-render (E3); CDN in front of Railway |
| Mosaic Lite license ambiguity | frontend | Pre-commit license check | Drop Mosaic Lite, use raw Tailwind |
| Rider disambiguation breaks when two riders with same slug (uncommon but possible) | backend riders endpoint | Contract test | Append race_number suffix to slug if collision |
| Existing `/2026/expert` link rot | backend redirects | E2E curl test in CI | 302 to /app/... |

### Failure Modes Registry

Merged into Error & Rescue table above.

### Dream State Delta

This plan ships ~30% of the 12-month ideal. Remaining 70% (comparison tool, filters, live results, admin UI, push, social shares) becomes 3-10x cheaper to build once Vue+FastAPI is in place. That's the real ROI of the refactor, not the initial parity.

---

## CLAUDE SUBAGENT (CEO — strategic independence) `[subagent-only]`

Independent subagent raised 10 findings with no prior-phase context. Critical/high summary:

| # | Finding | Severity |
|---|---|---|
| 1 | Wrong problem framing — ships zero new user value, adds SEO risk, build pipeline, bundle. Stated pain has no concrete user request behind it. | critical |
| 2 | Premise P7 (SPA for read-only site) is load-bearing and weak. If follow-on features don't materialize, refactor is pure cost. | critical |
| 3 | HTMX-on-FastHTML dismissed without analysis. Plan admits it was never compared. 2-3 day spike vs 1-2 week rewrite. | critical |
| 4 | SEO regression under-scoped. Niche-sport fans find race results via Google. SPA kills this unless SSR/pre-render day-one. | high |
| 5 | Mosaic Lite light→dark port cost hand-waved. Current 180-line CSS is being discarded for unclear design gain. | high |
| 6 | Nuxt 3 dismissed in one line. Gives Vue + SSR (fixes SEO risk). Claimed "more complex deploy" without evidence. | high |
| 7 | No rollback or traffic baseline. No canary. Phase 5 just says "merge to main, delete old code". | high |
| 8 | Scope mis-calibrated against near-term user value. Right-sized as infra; oversized for 1-3 month user visibility. | medium |
| 9 | "Do nothing" alternative not considered (invest the week in content instead of stack). | medium |
| 10 | October 2026 regret scenario: same features + Vue bundle + 30% organic drop + half-adapted Mosaic theme; unlock slipped. | high |

**Subagent recommended fix:** Either bundle the refactor with a committed user-facing feature and default to Nuxt SSR, or run a 2-3 day HTMX spike on the existing FastHTML stack first and measure the ceiling.

### Subagent Verdict (vs primary)

| Dimension | Primary | Subagent |
|---|---|---|
| Premises stated & sound | 5/10 | 3/10 |
| Right problem? | 7/10 | 4/10 |
| Scope calibration | 7/10 | 5/10 |
| Alternatives explored | 4/10 | 3/10 |
| Competitive/market risk | 7/10 | 5/10 |
| 6-month trajectory | 8/10 | 5/10 |

---

## CEO Dual Voices — Consensus Table

```
CEO DUAL VOICES — CONSENSUS TABLE                  (single-voice mode: Codex unavailable)
═══════════════════════════════════════════════════════════════
  Dimension                           Primary  Subagent  Consensus
  ──────────────────────────────────── ──────── ────────── ──────────
  1. Premises valid?                   PARTIAL  NO         DISAGREE (subagent stronger)
  2. Right problem to solve?           YES-ish  NO         DISAGREE — USER CHALLENGE
  3. Scope calibration correct?        YES      NO         DISAGREE — USER CHALLENGE
  4. Alternatives sufficiently        NO       NO         CONFIRMED (both flag gap)
     explored?
  5. Competitive/market risks         PARTIAL  NO         DISAGREE — SEO risk under-scoped
     covered?
  6. 6-month trajectory sound?         YES      NO         DISAGREE — conditional on follow-through
═══════════════════════════════════════════════════════════════
```

**Both voices agree (CONFIRMED, 1/6):** Alternatives under-explored — HTMX specifically, Nuxt as defensible default, and "do nothing" null alternative.

**Disagreements (5/6):** Subagent consistently pushes harder on whether the refactor should happen *now, as specified*. Primary voice accepts the current direction conditional on follow-through to dream-state features; subagent rejects accepting that condition without a written commitment.

---

## USER CHALLENGES (both voices agree direction should change)

### UC-1: Run an HTMX spike before committing to Vue rewrite

- **You said:** Rewrite to FastAPI + Vue 3 + Mosaic Lite as specified.
- **Both voices recommend:** Time-box a 1-2 day HTMX-on-FastHTML spike first. Implement one real interactive feature (e.g., live-filter standings). If the spike hits a clear ceiling, the rewrite is justified. If not, defer.
- **Why:** HTMX is ~10x less effort and keeps SEO + single-language stack. The plan never compared it.
- **What we might be missing:** Maybe you already decided the long-term platform belongs on Vue for reasons not in the plan (team familiarity, hiring, other projects, aesthetics).
- **If we're wrong, the cost is:** 2 days on an HTMX spike, decide Vue anyway, net loss = 2 days. If we're right, you save ~10 days.

### UC-2: Upgrade to Nuxt 3 SSR, or make pre-render a day-one Phase 2 requirement

- **You said:** Vue 3 SPA, SSR/pre-render in "Open follow-ups (out of scope)".
- **Both voices recommend:** For a public read-only site, SSR or pre-render is not optional. Either switch to Nuxt 3 (Vue ergonomics + SSR) or firmly commit pre-render to Phase 2.
- **Why:** Crawler traffic is the primary discovery channel for niche-sport content. SPA-without-SSR risks a measurable organic drop.
- **What we might be missing:** You may have traffic data showing most visitors arrive from direct links, not search.
- **If we're wrong, the cost is:** Nuxt adds ~2 days of setup but nothing else changes.

### UC-3: Bundle the refactor with at least one committed user-facing feature, or defer

- **You said:** Refactor alone. Features like comparison/filters/live results deferred.
- **Both voices recommend:** Ship the week's work WITH a visible new feature so users see the upgrade. Alternatively, defer the refactor until such a feature is greenlit.
- **Why:** A refactor that produces "same UX, slower first paint, broken SEO" is a regression from the user's perspective.
- **What we might be missing:** You may be planning the features for immediately after and see the refactor as pre-work you can't squeeze into the same window.
- **If we're wrong, the cost is:** Bundling adds 2-4 days of feature work but guarantees the week produces user-visible value.

---

## CEO Completion Summary

| Dimension | Primary | Subagent | Consensus |
|---|---|---|---|
| Premises stated & sound | 5/10 | 3/10 | DISAGREE |
| Right problem? | 7/10 | 4/10 | DISAGREE (USER CHALLENGE UC-3) |
| Scope calibration | 7/10 | 5/10 | DISAGREE (USER CHALLENGE UC-1) |
| Alternatives explored | 4/10 | 3/10 | CONFIRMED — both low |
| Competitive/market risk | 7/10 | 5/10 | DISAGREE — SEO risk (USER CHALLENGE UC-2) |
| 6-month trajectory | 8/10 | 5/10 | DISAGREE — conditional on follow-through |

**Verdict:** The plan is well-engineered but the "why now" is under-argued. Three user challenges (UC-1, UC-2, UC-3) go to the final approval gate. Premise gate stops Phase 2 from starting until you confirm or adjust direction.

---

## Premise Confirmation Gate — RESOLVED

User accepted **UC-2** (pre-render as Phase 2 hard requirement). UC-1 and UC-3 declined. Phase 2 and Phase 3 reviews proceeded against the updated plan.

---

# CEO Review — Extended Analysis (added after initial gate)

Additional product-strategy analyses added per user request:
- Stakeholder map (item 4)
- SEO priority confirmation (item 6)
- Monetization lens (item 8)
- Dream-state feasibility grading (item 9)
- Phasing decision (item 10)
- Competitive analysis with recommendations (item 5)
- Visit-data gap note (item 1 — gated on Railway CLI auth)
- Success metrics shortlist (item 3 — user to pick)
- **Emergent finding: stack reconsideration based on competitive evidence (item 7)**

---

## Stakeholders

| Who | Role | Interests |
|---|---|---|
| **You** | Solo owner + developer + decision-maker | Ship fast, keep SEO, enable future features, preserve brand |
| Race fans (primary users) | Consume standings + results + rider profiles | Fast mobile pages, search finds the right result, easy navigation |
| Riders | Subjects of profile pages | Accurate results, correct name/team/number, attractive presentation |
| Race organizers / BGX federation | Data authority, potential future sponsor | Data freshness, brand-appropriate presentation, reliability on race days |
| Future sponsors (per item 8) | Pay for visibility in future | Visual slots, brand-safe surroundings, traffic data to justify spend |
| SEO visitors (Google-driven) | Find race results via search | Server-rendered content, canonical URLs, fast FCP |

**Decision rights:** you alone. No committees.

---

## SEO Priority (confirmed)

Item 6 confirms: **SEO is a top concern.** This elevates:
- **UC-2 (pre-render hard requirement):** already accepted, stays.
- **Rollback criterion in Considerations §9:** stays. If post-launch organic traffic drops >25% for 14 days, upgrade to full SSR.
- **Any dynamic route not in the pre-render set** is an SEO risk vector — rider profiles specifically (300+ URLs, unbounded growth).
- **Stack reconsideration (see Emergent Finding below):** if a stack exists that ships zero JS by default, it SEO-beats the pre-rendered Vue SPA.

---

## Monetization Lens (item 8: future sponsors)

Design implications of future sponsor revenue:

| Need | Implication |
|---|---|
| Sponsor logo slots | Reserve horizontal rail on nav or above-table for logos (top-of-fold visibility). Standard motorsport pattern per competitive analysis. |
| Event sponsorship | Event detail pages could carry a per-event sponsor block (top of page). |
| Category sponsorship | Category pages could carry a per-category brand lock-up. |
| Brand safety | No UGC (user comments, ratings) in scope now — keeps brand-safe. |
| Traffic data for sales | The `/stats` endpoint + external analytics become revenue-supporting. Make it robust (auth fix per Eng SC-1 is now revenue-relevant, not just hygiene). |
| Partner co-branding | FIM Hard Enduro shows "Plews / WEO / S3 / Factory Days" sponsor rail. Copying this pattern is on-genre. |

**No short-term build impact** — these are slots to be aware of while designing layouts, not Phase 1 work. But: design the header/hero/side-rail with future sponsor integration in mind (don't paint into a corner with a tight hero card that has no room).

---

## Dream-State Feasibility Grading (item 9)

Grading the 9 dream-state features (all except live results, per user):

| Feature | Feasibility | Scope (CC) | Required input |
|---|---|---|---|
| Rider comparison tool | Realistic solo | ~1-2 days | Design of the compare widget |
| Filters on standings (team/bike/age group) | Realistic solo | ~4-8h | Data completeness (are team/age fields populated?) |
| Progression charts (per rider across events) | Realistic solo | ~1 day | Chart library choice (probably ECharts or Chart.js as island) |
| Mobile-first responsive | Realistic — now | ~4-8h per view | Part of the refactor itself (UD-5 from design review) |
| Admin UI (replaces import scripts) | Realistic solo | ~2-3 days | Auth decision (same gate as /stats) |
| Social share images (per rider / event) | Realistic solo | ~1 day | OG-image template + serverless image generation (or Cloudinary) |
| Race-day timing system integration | **Needs partner** — external timing system needed | 2-5 days once partner exists | Which timing system? (Raceresult.com? Custom?) |
| Push notifications (race day) | Aspirational — web push works but iOS limits; need PWA | 2-3 days | Service worker + notification design |
| ~~Live results WebSocket~~ | **Removed from dream state per user item 9** | — | — |

**Post-refactor roadmap priority (rough):**
1. Social share images (quick monetization signal)
2. Filters on standings (high user value, low cost)
3. Progression charts (showcase)
4. Rider comparison (delight)
5. Admin UI (ops cost reduction)
6. Push notifications (event-day retention)
7. Race-day timing (event-day killer feature — conditional)

---

## Phasing Decision (item 10)

**User chose: Ship refactor alone; features follow.**

Accepted. UC-3 (bundle-with-a-feature) declined.

Mitigation to address subagent's concern that "a week of work produces zero user-visible change":
- Phase 2 *should* produce visible polish even in a parity refactor — the dark Mosaic Lite theme is new, the podium treatments can be upgraded with the motorsport-identity guardrails (per design-review.md D6).
- Make sure the first post-refactor feature ship is scheduled and committed on paper (e.g., "filters in week 3"). Don't leave it as "someday" or the subagent's regret scenario materializes.

---

## Competitive Analysis — Findings + Recommendations

Live-examined: MXGP.com, FIM Hard Enduro, Supercross Live, Dakar.com, BGX.bg (incumbent).

### Summary

| Site | Standings style | Rider profile | Mobile | SSR/SPA | Interactivity | Monetization |
|---|---|---|---|---|---|---|
| **MXGP results** | Dense light table, ASP.NET legacy | Race # + career-year results + team chips | Poor reflow | SSR (.aspx) | Season/class/race dropdowns | Banner ads + sponsor strip |
| **FIM Hard Enduro** | **Dark theme, hero portrait of class leader with "1" + points + flag**, plain rows below | Roster table | Good single-column reflow | WordPress SSR | Minimal season picker | Sponsor logo rail |
| **Supercross Live** | Dark, teal accents, round × class matrix | Separate /riders/ section | Responsive | WordPress SSR | Year/class tabs, fantasy + betting + live-timing | Monster Energy co-branding, tickets, fantasy app |
| **Dakar** | Orange/black, **category pill-toggles**, stage picker, BIB search, "See more" pagination | Competitor detail with team/time/penalty | **Excellent mobile reflow** — pills wrap, rows stack | Custom SSR + hydration | Stage picker, BIB/name search, category toggles | "by TUDOR" timing lockup, sponsor-integrated |
| **BGX.bg incumbent** | **PDF archive only** | None | n/a | PHP SSR | Language picker | None |

### Three patterns worth stealing

1. **FIM Hard Enduro leader hero card.** Top of each class: bold portrait of current leader with "1" number, name, total points, flag — then plain rank rows below. Converts a table into a story. BGX already has gold podium metallics; extend to a hero treatment for class leaders.

2. **Dakar pill-toggle class switcher + stage dropdown.** One URL with instant client-side filtering across categories. BGX has 8 classes — same shape problem, same solution. Can keep SSR per-class URL (for SEO) AND add instant pill swap (no nav) for good UX.

3. **Supercross season matrix on rider profile.** Compact per-event results strip: "R1: 3rd / R2: DNF / R3: 1st / R4: …" Dense and scannable. Way better than prose season summaries.

### Three patterns to avoid

1. **MXGP's legacy dense table.** 25 columns, 10px font, horizontal scroll. Hard no.
2. **Ad/sponsor clutter above the fold** (MXGP, Dakar). Don't push results below a sponsor bar on mobile. Put sponsors in the sidebar or below the hero, not above the standings.
3. **BGX.bg's "results = PDF archive"** (the incumbent). The thing being replaced. Stay data-first, render HTML tables; PDFs are export-only.

### Motorsport visual vocabulary

Genre splits into two camps:
- **"FIA/FIM premium dark"** (Dakar, FIM Hard Enduro, Supercross, F1.com) — near-black, one aggressive accent (Dakar=orange, HEWC=red, Supercross=teal), bold condensed sans (Barlow/Oswald/Teko), portrait photography, flag chips, metallic podium colors.
- **"Legacy federation light"** (MXGP results, BGX.bg) — white/blue, Arial, table-first, dated.

**BGX's direction — dark + gold + silver/bronze podium — fits the premium dark camp perfectly. Gold is distinctive** (Dakar=orange, HEWC=red, Supercross=teal) and signals "championship trophy" better than any. Keep this direction; just execute it with big condensed type, portrait-led hero cards, and flag chips.

---

## EMERGENT FINDING — Stack reconsideration (item 7 + competitive evidence)

**User item 7:** "I am ok to use easier to use technology that makes sense. Should be quicker to implement and have better performance."

**Competitive evidence:** 0 out of 6 comparable sites run a Vue/React/SPA for standings. All run SSR (WordPress, Drupal, ASP.NET, custom SSR + partial hydration). The SPA-at-all-costs pattern is not in the genre.

This is a **signal to reconsider the stack choice itself.** The current plan (FastAPI + Vue 3 SPA with 25 pre-rendered routes) is:
- Heavier than any competitor
- Requires a build pipeline, pre-render DB dance, bundle budget, hydration timing
- Ships unused JS on pages where users just read a table

**Alternative stacks worth considering given item 7:**

| Stack | Lines of JS shipped for standings | SEO | Simplicity | Future features | Dev speed |
|---|---|---|---|---|---|
| **FastAPI + Vue 3 SPA + pre-render (current plan)** | ~80-150 KB gzipped | Pre-render for 25 routes, CSR fallback for rest | Medium-high (Vite, Vue, Router, Pinia, Vite plugin, pre-render config) | Good | Medium |
| **FastAPI + HTMX + Alpine.js** (UC-1 direction) | ~15 KB gzipped total | Full SSR per-page, perfect SEO | Low | Medium ceiling | **Fastest** |
| **FastAPI + Jinja2 + HTMX + Alpine** | Same | Full SSR | Lowest | Medium | Fastest |
| **Astro + FastAPI (JSON backend)** | **~0 KB by default; opt-in hydration per "island"** | SSG per route, perfect SEO | Low-medium | **Best** (Vue/Svelte/React/Preact components as islands) | Fast |
| **Nuxt 3 SSR + FastAPI** | ~60-80 KB gzipped | Full SSR | Medium-high | Excellent | Medium |

**My recommendation given user constraints (SEO priority, easier tech, better perf, future sponsor monetization):**

→ **Astro + FastAPI is the best fit.**

Why:
- Astro is content-first: by default ships 0 KB of JS. Each page is pre-rendered to static HTML at build time. Best possible SEO for standings/rider pages. Best possible FCP (no hydration wait).
- Astro islands: when you need interactivity (class pill switcher, filters, rider comparison, progression charts), you hydrate ONE component using Vue/React/Svelte/Preact. The rest stays static HTML.
- Simpler mental model than Vue SPA: "it's just HTML with components." No Pinia, no Router, no Pre-render plugin, no SSR hydration timing.
- Matches the competitive pattern: Dakar + Supercross + HEWC all feel like "SSG with sprinkled interactivity" — that's literally what Astro is.
- Future features:
  - Filters on standings → Vue island on the standings page
  - Rider comparison → one page, one Vue island
  - Social share images → Astro's `@astrojs/image` or serverless OG generator at build time
  - Progression charts → Chart.js island
- Deployment: single container, multi-stage Docker (Node build → Python runtime), FastAPI serves /api/* and static files. Or Astro can run on Node at runtime (Astro SSR mode) if needed.

**Cost of switching to Astro:** none of the plan's phases change shape. Phase 0 (repo reshape), Phase 1 (FastAPI JSON API), Phase 4 (single-container deploy), Phase 5 (cutover) are identical. Only Phase 2 (frontend scaffold) and Phase 3 (view ports) change — Astro pages instead of Vue views.

**Honest trade-off:** Vue + Mosaic Lite gives a more "full-stack SPA feel" if you later want a richly interactive app (e.g., admin dashboard with complex state). For a read-heavy content site with occasional interactive widgets, Astro is strictly better. If the 12-month dream state stays read-heavy (as graded above), Astro wins.

→ **This is a potential USER CHALLENGE UC-4.** Raising it because item 7 explicitly opened the door.

---

## Visit-Data Gap (item 1)

**Status:** data not retrieved — Railway CLI needs auth + no local Postgres running + `psql` not on PATH.

When you have time, these three queries would inform the CEO review's risk model:

```sql
-- Q1: top 20 most-visited pages in the last 30 days
SELECT page, COUNT(*) AS hits
FROM visit
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY page
ORDER BY hits DESC
LIMIT 20;

-- Q2: mobile/desktop split, overall + by page type
SELECT device_type, COUNT(*) AS visits, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM visit
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY device_type
ORDER BY visits DESC;

-- Q3: bounce proxy — single-page visits per device_type
-- (needs session reconstruction; a rough proxy: % of visits where page contains "/r/" vs not)
SELECT
  device_type,
  COUNT(*) FILTER (WHERE page LIKE '%/r/%') AS rider_page_hits,
  COUNT(*) FILTER (WHERE page NOT LIKE '%/r/%') AS other_hits
FROM visit
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY device_type;
```

Run with: `railway login && railway link && railway run psql $DATABASE_URL -f queries.sql` — or copy SQL into Railway's built-in query console for the Postgres plugin.

**Implication if data shows:**
- Mostly mobile → mobile-first design is critical (already in Phase 2 requirements).
- Mostly rider-profile traffic → those pages must be SSR/SSG (Astro solves this; Vue SPA + pre-render doesn't cover unbounded rider profiles).
- Low repeat visits → SEO is THE primary traffic channel (UC-2 fully justified, possibly UC-4 too).

**Treat as a Day-0 task before Phase 2 starts.** 10 minutes of querying = better-calibrated plan.

---

## Success Metrics — Shortlist (item 3 — user to pick)

Candidates, grouped by category:

### Performance (page speed)
- **M1** — **Time to First Byte (TTFB)** — server response speed. Current ~100-200ms from Railway EU.
- **M2** — **Largest Contentful Paint (LCP)** — when the main content appears. Target <2.5s (Google "Good").
- **M3** — **Cumulative Layout Shift (CLS)** — visual stability. Target <0.1.
- **M4** — **Interaction to Next Paint (INP)** — responsiveness to clicks. Target <200ms.
- **M5** — **Bundle size (JS gzipped)** — shipped per page. Baseline 0 KB (current), target depends on stack.

### Discoverability (SEO)
- **M6** — **Organic search sessions (Google)** — weekly, from Search Console.
- **M7** — **Indexed pages count** — how many BGX URLs Google knows about.
- **M8** — **Average position for target queries** — "BGX 2026 expert", rider names, etc.
- **M9** — **Click-through rate on Search Console impressions** — are our snippets attractive?

### Engagement
- **M10** — **Visits per week (from `Visit` table)** — overall traffic trend.
- **M11** — **Mobile session share** — % of visits on mobile.
- **M12** — **Deep visits** — visits that navigate >1 page (proxy for engagement).
- **M13** — **Event-day spike** — multiplier of baseline traffic on a race weekend.

### Dev velocity (post-refactor)
- **M14** — **Time to ship a new feature** — e.g., "add filters" — on new stack vs estimated on current.
- **M15** — **Frontend commits per week** — proxy for feature velocity.
- **M16** — **Production bugs per month** — refactor shouldn't introduce regressions.

### Business (future monetization)
- **M17** — **Demographic metrics for sponsor sales** — unique visitors, sessions/month, top geographies.
- **M18** — **Page-visits-per-event-page** — sponsor pitch metric.

---

## Risk Matrix (Probability × Impact)

| Risk | P | I | Score | Mitigation |
|---|---|---|---|---|
| SEO regression post-launch (SPA without SSR) | 40% | HIGH | ⚠️ **9** | Pre-render (Phase 2 hard req) + rollback criterion; **eliminated if Astro adopted** |
| `/stats` endpoint exposes analytics data (no auth today) | 100% | MEDIUM | ⚠️ **8** | HTTP Basic Auth + env var (Eng SC-1, ~30 min) |
| Mount-order bug makes `/api/nonexistent` serve index.html | 30% | MEDIUM | 5 | Explicit mount order + test (Eng A-1) |
| Pre-render needs DB at build time (Railway has none) | 100% | MEDIUM | ⚠️ **8** | Commit `prerender-routes.json` or use staging API (Eng P-2); **eliminated if Astro with static routes adopted** |
| Mosaic Lite license ambiguity | 10% | MEDIUM | 2 | Day-0 audit; fall back to raw Tailwind |
| Slug mutation breaks existing links | 40% | HIGH | 8 | Pin current `_rider_slug` algorithm exactly (Eng CQ-1) |
| Bundle size blowout (Mosaic + Vue + deps) | 50% | MEDIUM | 5 | CI size-limit gate (Eng P-1) |
| Visit tracking regresses silently | 30% | LOW | 2 | Integration test asserting Visit row on /app/* visit |
| POST /api/track flood writes unbounded rows | 20% | MEDIUM | 3 | Payload cap + rate-limit (Eng SC-2) |

**Top-3 risks:** SEO regression, `/stats` exposure, pre-render DB dependency. All addressable; two of them **disappear if the stack switches to Astro SSG**.

---

## Decision Reversibility Matrix

| Decision | Reversibility | Effort to change later | Implication |
|---|---|---|---|
| Framework (Vue SPA vs Astro vs HTMX) | **Hard** | ~1-2 weeks (rewrite Phase 2 + 3) | **Decide carefully now.** |
| Deployment topology (single service) | Easy | <1 day | Revisit freely as the app grows |
| URL scheme (`/app/*` prefix) | Easy | Redirects are cheap | Low stakes |
| Repo layout (monorepo) | Easy | Migration scripts exist | Low stakes |
| CSS framework (Tailwind + Mosaic) | Medium | ~1 week to swap | Mid-stakes; tokens survive via DESIGN.md |
| Database (Postgres) | Very hard | Major migration | Not being changed; stable |
| Authentication scheme on `/stats` | Easy | <1h | Low stakes |
| Slug algorithm | **Very hard** (after publish) | Redirect table required | **Must pin NOW** |

The one truly hard decision is the framework. Given item 7 opens the door to reconsideration AND competitive evidence strongly supports SSR/SSG, the framework question should be revisited before Phase 2 starts.

---

## Revised User Challenges (updated)

| UC | Recommendation | User response |
|---|---|---|
| UC-1 | HTMX spike before Vue rewrite | Rejected |
| UC-2 | SSR or day-one pre-render | **Accepted** — originally as pre-render; now satisfied natively by UC-4 |
| UC-3 | Bundle with a user-facing feature | Rejected (ship refactor alone, features follow) |
| **UC-4** | **Switch from Vue 3 SPA to Astro** | **ACCEPTED** — plan restructured |

---

## Summary Additions

**Settled per user input:**
- Stakeholder = solo (you)
- SEO = top priority
- Monetization = future sponsors (design with slots in mind)
- Dream-state grading = all feasible except live results
- Phasing = refactor alone, features follow (UC-3 declined)

**Gathered:**
- Competitive analysis: SSR is genre-standard; 0/6 comparable sites run SPAs
- Risk matrix: 3 top risks (SEO, /stats, pre-render DB); 2 of 3 removed by Astro
- Decision reversibility: framework is the only truly hard decision

**Resolved:**
- **UC-4 accepted:** stack switched Vue 3 SPA → Astro SSG. Plan restructured.
- **Success metrics locked:** M1 LCP, M2 bundle size, M3 organic sessions, M4 indexed pages, M5 visits/week, M6 mobile share, M7 time-to-ship-next-feature.

**Outstanding:**
- Visit-data baseline queries (blocked on Railway auth — user runs when ready; Pre-launch checklist in main plan)
- `/stats` auth fix (Eng SC-1 critical) — applied during Phase 1
- Pre-Phase-2 design artifacts D1-D10 (DESIGN.md, view-anatomy, states-matrix, identity guardrails, responsive contract) per design-review.md
