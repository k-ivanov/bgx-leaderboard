# SEO optimizations for hardendurobulgaria.com

## Context

The dashboard already has a substantial SEO baseline — sitemap (495 entries), robots.txt, canonical URLs, Open Graph + Twitter cards on every page, per-page title/description templates in `copy.ts`, and `Person` + `SportsTeam` JSON-LD on rider profiles. `design-review.md §18` specs the intended SEO surface; most of it is implemented.

This plan groups the remaining gaps by impact-vs-effort. Each tier is independently shippable. Pick what matters; skip the rest.

## Audit summary

**Already in place** (don't touch):
- Sitemap at `/sitemap-index.xml` and `/sitemap.xml` (495 URLs)
- `robots.txt` with `Disallow: /stats` and `Disallow: /api/`
- `<link rel="canonical">` on every page (`BaseLayout.astro:113`)
- OG + Twitter cards on every page (`BaseLayout.astro:123–133`)
- Per-page title and description templates for every view (`copy.ts` `seo` namespace)
- `Person` + `SportsTeam` JSON-LD on `/rider/{slug}` (`rider/[slug].astro:78`)
- Single shared `og-default.png` (1200×630, on-brand) — shipped earlier today
- `lang="bg"` on `<html>`
- Astro SSG → fast first paint, low CLS
- Cloudflare Web Analytics installed (RUM data feeds back to us)

**Gaps to address**: tiers below.

---

## Tier 1 — High impact, low effort (ship first)

### 1. `BreadcrumbList` JSON-LD on every nested page

Google renders breadcrumbs in SERP results. Boosts CTR and visual prominence.

- **Files**: `frontend/src/layouts/BaseLayout.astro` (accept a new `breadcrumbs?: Array<{name, url}>` prop, emit a second `<script type="application/ld+json">` when present).
- **Pages to wire up**: `results.astro`, `rider/[slug].astro`, the future race-overview/race-results pages if they exist as separate routes.
- **Pattern**:
  ```json
  {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
    {"@type":"ListItem","position":1,"name":"Начало","item":"https://hardendurobulgaria.com/"},
    {"@type":"ListItem","position":2,"name":"Резултати","item":"https://hardendurobulgaria.com/results"},
    ...
  ]}
  ```
- **Effort**: ~30 min including tests.

### 2. `WebSite` + `SearchAction` JSON-LD on homepage

Enables Google's site-link search box (the in-result search widget under the brand name).

- **File**: `frontend/src/pages/index.astro` — add a `jsonLd` object.
- **Pattern**:
  ```json
  {"@context":"https://schema.org","@type":"WebSite",
   "url":"https://hardendurobulgaria.com/",
   "name":"Шампионат БГХ Хард Ендуро",
   "potentialAction":{
     "@type":"SearchAction",
     "target":"https://hardendurobulgaria.com/results?season={search_term_string}",
     "query-input":"required name=search_term_string"
   }}
  ```
- **Effort**: ~10 min.

### 3. 301 redirect from old name-only rider slugs to new full slugs

Earlier today we moved from `иван-иванов` to `иван-иванов-191`. Old URLs in social shares, search index, and bookmarks now 404. Search engines drop indexed pages and link equity decays. Add a fallthrough on `/rider/{old-slug}`: if exactly one Rider matches by name, 301 to their canonical full slug; if multiple, render a small disambiguation page or pick the most recent.

- **File**: `backend/app/redirects.py` (or a new `riders_redirect_router`). Match `/rider/{slug}` ahead of `StaticFiles`. Strip a numeric suffix; if there's no suffix and exactly one Rider has that name slug, 301 to the canonical full-slug URL. If zero or multiple, fall through to the static 404 page.
- **Test**: `backend/tests/test_redirects.py` — pin a 301 from `/rider/димитър-тинчев` → `/rider/димитър-тинчев-255`.
- **Effort**: ~45 min.

### 4. `noindex` + canonical on `/compare?a=&b=` permutations

The compare page (just shipped on `feature/compare-riders`) takes two slugs as query params. Without action, Google would index `O(n²)` URLs that all share content. Two complementary moves:

- Pass `noindex={true}` to `BaseLayout` from `compare.astro` whenever query params are present (or just always, since the empty page has no useful indexable content).
- Set canonical to `https://hardendurobulgaria.com/compare` (no params) so shared canonical link equity collects on one URL.
- **Files**: `frontend/src/pages/compare.astro` + `frontend/src/components/CompareView.vue` (the latter to update the canonical via `<link>` injection if Astro's static layer can't see the query).
- **Effort**: ~20 min. Revisit later if comparison URLs become valuable to surface in SERP.

### 5. Per-page `lastmod` in sitemap based on data, not build date

Today every URL in `/sitemap.xml` shares `lastmod` = build date. Search engines deprioritize re-crawl when `lastmod` doesn't actually change. The fix: in `frontend/scripts/build-sitemap.mjs`, fetch the API at sitemap-build time to pull a per-rider / per-race "data updated at" timestamp (most recent `event_date` in their results, or just `max(EventResult.imported_at)` if we add it).

- **Cheaper interim**: bucket lastmod by year. Riders/races in 2026 get today's date; 2024-only entries get `2024-12-31`. Already directionally correct.
- **File**: `frontend/scripts/build-sitemap.mjs`.
- **Effort**: ~30 min for the bucketed version; ~2 hr for the per-row version with backend work.

---

## Tier 2 — High impact, medium effort

### 6. `SportsEvent` JSON-LD on race pages

If/when there's a per-race overview page (e.g. `/results?race=…` opens a race-detail view), add `SportsEvent` structured data with `startDate`, `endDate`, `location`, `organizer`, `competitor`. Per `design-review.md §18.5` this is part of the spec. Big for queries like "хард ендуро бухово 2025".

- **File**: where the race overview is rendered in `ResultsView.vue` or a separate Astro page. Inject as JSON-LD via the BaseLayout prop.
- **Effort**: ~1.5 hr.

### 7. Per-page generated Open Graph images

Currently all pages share the static `og-default.png` (logo on black). Generated per-page cards lift social CTR substantially.

- **`/rider/{slug}`**: rider name, race number, "BGX Хард Ендуро · {latest year} · {latest category}".
- **`/results?season=…&category=…`**: "Класиране · {category} · {year}", podium-implied accent.
- **`/results?…&race=…`**: race name + year.
- **Tooling**: build-time generator with `@vercel/og` (Satori-based, no canvas dep) or a small Pillow script. Output to `dist/og/{slug}.png`. Update `BaseLayout` to accept `ogImage` per page, default to `/og-default.png`.
- **Effort**: ~3 hr — image generator setup is the bulk of it.

### 8. Internal linking expansion

Crawlers discover content via links, and PageRank flows along them. Current pages link OK (rider → seasons; results → riders) but could be denser:

- Every rider profile season row should link to the category leaderboard for that season (already does — verify and extend).
- Every rider profile should link to "other riders in the same category" (top 5) to spread crawl coverage and stickiness.
- Race overview should link to standings for every category that ran in that race.
- Add prev/next race navigation on race pages (already specced in `design-review.md`; verify it exists).
- **Effort**: ~2 hr depending on how much already exists.

---

## Tier 3 — Verify + polish

### 9. Lighthouse 100/100/100/100 on all public routes

`design-review.md §22` sets the gate. Run Lighthouse against `/`, `/results?season=2025`, `/rider/{popular-slug}` on a mid-tier mobile profile. If anything drops below 95, fix before considering the SEO work "done."

- Likely culprits: image LCP (verify `loading="eager"` only on hero), unused JS in islands, CLS on font swap.
- **Effort**: ~1 hr to audit; fixes vary per finding.

### 10. Rich Results Test pass

After adding the JSON-LD changes from Tier 1, run https://search.google.com/test/rich-results on a rider page, the homepage, and (if added) a race page. Fix any structured-data warnings — they're often subtle (missing `image`, malformed dates).

- **Effort**: ~30 min.

### 11. Search Console hygiene

If not already: verify the property in Google Search Console, submit `/sitemap-index.xml`, monitor coverage report for 404s post-slug-change. The slug-change deploy will surface a wave of 404s; the redirect from item 3 deflects them, but Search Console reports lag by days.

- **Effort**: ~15 min one-time setup.

---

## Tier 4 — Lower priority / defer

- **`hreflang`**: single-language site, skip.
- **`Organization` JSON-LD**: minor benefit, can ship in Tier 1 if extending the home-page JSON-LD anyway.
- **AMP**: dead, skip.
- **Pagination meta**: leaderboards aren't paginated.

---

## Critical files

| Concern | File |
|---|---|
| Per-page meta + JSON-LD plumbing | `frontend/src/layouts/BaseLayout.astro` |
| SEO copy templates | `frontend/src/lib/copy.ts` (`seo` namespace) |
| Homepage JSON-LD wiring | `frontend/src/pages/index.astro` |
| Rider profile JSON-LD wiring | `frontend/src/pages/rider/[slug].astro` |
| Sitemap generator | `frontend/scripts/build-sitemap.mjs` |
| Old-slug redirect router | `backend/app/redirects.py` (extend) |
| Compare-page noindex + canonical | `frontend/src/pages/compare.astro`, `frontend/src/components/CompareView.vue` |
| OG image generator (Tier 2) | new: `frontend/scripts/build-og-images.mjs` |
| Spec source of truth | `.plan/design-review.md` §18, §22 |

## Verification

- `curl https://hardendurobulgaria.com/sitemap.xml | grep -c '<url>'` — confirm count grows after Tier 1 (no change expected) and after compare-pages excluded.
- `curl https://hardendurobulgaria.com/ | grep -oE '@type":"[^"]+"' | sort -u` — should show `WebSite` after Tier 1 #2; `BreadcrumbList` after #1; previously only `Person`+`SportsTeam` on rider pages.
- Rich Results Test (https://search.google.com/test/rich-results?url=…) on each page type — should report breadcrumbs / sitelinks search box / person valid.
- `curl -I https://hardendurobulgaria.com/rider/димитър-тинчев` — should `301` to `/rider/димитър-тинчев-255` after Tier 1 #3.
- Lighthouse on mobile (`npx lighthouse https://hardendurobulgaria.com --view --form-factor=mobile`) — expect SEO 100, Performance ≥ 95.
- After 2 weeks: Search Console "Coverage" report should show indexed-page count holding (not dropping post-slug-change), and any 404 spike should clear out.

## Recommended order

1. Tier 1 #4 (compare page noindex) — protects against indexing the just-shipped feature.
2. Tier 1 #3 (old-slug redirects) — protects against the slug-change deploy losing link equity.
3. Tier 1 #1 + #2 (BreadcrumbList + WebSite JSON-LD) — biggest CTR impact, lowest cost.
4. Tier 1 #5 (sitemap lastmod buckets) — quick win for crawl prioritization.
5. Tier 2 #7 (per-page OG images) — biggest social-share lift, but a real chunk of work; do once Tier 1 settles.
6. Tier 2 #6 + #8 + Tier 3 — when there's time.
