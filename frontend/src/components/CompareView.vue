<script setup lang="ts">
// Compare two riders side-by-side. Reads ?a=&b= from the URL, fetches
// each rider's full multi-season career via /api/riders/career, then
// composes:
//   - a stats card per rider (career totals)
//   - a head-to-head table (only events both riders entered)
//
// Both, one, or neither slug may be present:
//   - neither → render two CompareSearch slots with "vs" between them
//   - one only → show that rider's name + a single CompareSearch
//   - both → load both careers, render the comparison
//
// No new backend endpoint; the existing /api/riders/career covers
// everything.
import { computed, onMounted, ref, watch } from 'vue';
import CompareSearch from './CompareSearch.vue';
import type { RiderCareerOut, RiderCareerSeasonOut, RiderSearchResultOut } from '~/lib/api.types';
import { copy } from '~/lib/copy';

const slugA = ref<string | null>(null);
const slugB = ref<string | null>(null);
const careerA = ref<RiderCareerOut | null>(null);
const careerB = ref<RiderCareerOut | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

function readUrl() {
  const u = new URL(window.location.href);
  slugA.value = u.searchParams.get('a');
  slugB.value = u.searchParams.get('b');
}

function pushUrl(a: string | null, b: string | null) {
  const u = new URL(window.location.href);
  if (a) u.searchParams.set('a', a); else u.searchParams.delete('a');
  if (b) u.searchParams.set('b', b); else u.searchParams.delete('b');
  window.history.pushState({}, '', u.toString());
  slugA.value = a;
  slugB.value = b;
}

async function fetchCareer(slug: string): Promise<RiderCareerOut | null> {
  const url = `/api/riders/career?slug=${encodeURIComponent(slug)}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  return (await res.json()) as RiderCareerOut;
}

async function loadBoth() {
  if (!slugA.value || !slugB.value) {
    careerA.value = null;
    careerB.value = null;
    return;
  }
  if (slugA.value === slugB.value) {
    error.value = copy.compare.sameRiderError;
    careerA.value = null;
    careerB.value = null;
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const [a, b] = await Promise.all([
      fetchCareer(slugA.value),
      fetchCareer(slugB.value),
    ]);
    if (!a || !b) {
      error.value = copy.compare.riderNotFound;
      careerA.value = null;
      careerB.value = null;
      return;
    }
    careerA.value = a;
    careerB.value = b;
  } finally {
    loading.value = false;
  }
}

function onPickA(r: RiderSearchResultOut) {
  pushUrl(r.rider.slug, slugB.value);
}
function onPickB(r: RiderSearchResultOut) {
  pushUrl(slugA.value, r.rider.slug);
}

// Aggregate helpers ---------------------------------------------------------

interface CareerStats {
  seasons: number;
  starts: number;
  finishes: number;
  bestOverall: number | null;     // lowest position across all results
  totalPoints: number;
  categoriesByYear: string;       // e.g. "Експерт · 2024, 2025"
}

function buildStats(career: RiderCareerOut): CareerStats {
  const seasons = career.seasons.length;
  const starts = career.seasons.reduce((acc, s) => acc + s.races_participated, 0);
  const finishes = career.seasons.reduce(
    (acc, s) => acc + s.results.filter(r => r.position != null).length,
    0,
  );
  const positions = career.seasons
    .flatMap(s => s.results.map(r => r.position))
    .filter((p): p is number => p != null);
  const bestOverall = positions.length > 0 ? Math.min(...positions) : null;
  const totalPoints = career.seasons.reduce((acc, s) => acc + (s.total_points ?? 0), 0);

  // "Експерт · 2024, 2025; Профи · 2026" — group by category display name.
  const byCat = new Map<string, number[]>();
  for (const s of career.seasons) {
    const list = byCat.get(s.category.display_name) ?? [];
    list.push(s.season_year);
    byCat.set(s.category.display_name, list);
  }
  const categoriesByYear = [...byCat.entries()]
    .map(([cat, years]) => `${cat} · ${years.sort().join(', ')}`)
    .join(' · ');

  return { seasons, starts, finishes, bestOverall, totalPoints, categoriesByYear };
}

// Head-to-head intersection -------------------------------------------------

interface H2HRow {
  key: string;             // "${year}-${event_slug}"
  year: number;
  eventName: string;
  categoryCode: string;    // for the link target; rider A's category in this event
  eventSlug: string;
  posA: number | null;
  posB: number | null;
  // winner: 'a' | 'b' | 'tie'
  winner: 'a' | 'b' | 'tie';
}

function flattenResults(career: RiderCareerOut) {
  // Map keyed on "${year}-${event_slug}-${category_code}" — including
  // category in the key so the intersection only matches when both
  // riders were competing in the same class. Comparing an expert
  // result against a women's-category result in the same race isn't
  // a head-to-head, it's a coincidence of date.
  const out = new Map<string, { season: RiderCareerSeasonOut; result: typeof career.seasons[number]['results'][number] }>();
  for (const s of career.seasons) {
    for (const r of s.results) {
      const cat = r.category?.code ?? s.category.code;
      out.set(`${s.season_year}-${r.event.slug}-${cat}`, { season: s, result: r });
    }
  }
  return out;
}

const h2hRows = computed<H2HRow[]>(() => {
  if (!careerA.value || !careerB.value) return [];
  const flatA = flattenResults(careerA.value);
  const flatB = flattenResults(careerB.value);
  const rows: H2HRow[] = [];
  for (const [key, a] of flatA) {
    const b = flatB.get(key);
    if (!b) continue;
    const posA = a.result.position;
    const posB = b.result.position;
    let winner: 'a' | 'b' | 'tie';
    if (posA != null && posB != null) {
      winner = posA < posB ? 'a' : (posB < posA ? 'b' : 'tie');
    } else if (posA != null) {
      winner = 'a';
    } else if (posB != null) {
      winner = 'b';
    } else {
      winner = 'tie';
    }
    rows.push({
      key,
      year: a.season.season_year,
      eventName: a.result.event.name,
      categoryCode: a.season.category.code,
      eventSlug: a.result.event.slug,
      posA,
      posB,
      winner,
    });
  }
  // Most recent first.
  rows.sort((x, y) => (y.year - x.year) || x.eventName.localeCompare(y.eventName));
  return rows;
});

const h2hSummary = computed(() => {
  const wins = { a: 0, b: 0, tie: 0 };
  for (const row of h2hRows.value) wins[row.winner] += 1;
  return wins;
});

const statsA = computed(() => careerA.value ? buildStats(careerA.value) : null);
const statsB = computed(() => careerB.value ? buildStats(careerB.value) : null);

function fmtPos(p: number | null): string {
  if (p == null) return copy.raceResults.dnf;
  return `${p}-и`;
}

function fmtBest(p: number | null): string {
  return p == null ? copy.common.noTime : `${p}-и`;
}

function nameA(): string {
  return careerA.value ? `${careerA.value.first_name} ${careerA.value.last_name}` : '';
}
function nameB(): string {
  return careerB.value ? `${careerB.value.first_name} ${careerB.value.last_name}` : '';
}

function raceLink(row: H2HRow): string {
  // Link the head-to-head row to that race's results page in the
  // category rider A raced. Cheap useful nav for the user who wants
  // to see the full field.
  return `/results?season=${row.year}&category=${encodeURIComponent(row.categoryCode)}&race=${encodeURIComponent(row.eventSlug)}`;
}

onMounted(() => {
  readUrl();
  void loadBoth();
  window.addEventListener('popstate', () => {
    readUrl();
    void loadBoth();
  });
});

watch([slugA, slugB], () => {
  void loadBoth();
});
</script>

<template>
  <section class="mx-auto max-w-4xl px-4 py-8 md:py-12">
    <h1 class="text-3xl md:text-4xl font-extrabold tracking-[-0.02em] uppercase mb-6">
      {{ copy.compare.h1 }}
    </h1>

    <!-- Empty state: nobody picked yet -->
    <div v-if="!slugA && !slugB" class="space-y-4">
      <p class="text-fg-muted">{{ copy.compare.pickBoth }}</p>
      <div class="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-center gap-3 md:gap-4">
        <CompareSearch
          variant="wide"
          :placeholder="copy.compare.pickFirstPlaceholder"
          @select="onPickA"
        />
        <span class="text-center text-fg-faint uppercase tracking-[0.06em] text-sm">
          {{ copy.compare.versus }}
        </span>
        <CompareSearch
          variant="wide"
          :placeholder="copy.compare.pickSecondPlaceholder"
          @select="onPickB"
        />
      </div>
    </div>

    <!-- One picked, asking for the second -->
    <div v-else-if="slugA && !slugB" class="space-y-4">
      <p class="text-fg-muted">
        <span class="font-semibold text-fg">{{ careerA?.first_name }} {{ careerA?.last_name }}</span>
        {{ ' ' }}{{ copy.compare.versus }}{{ ' …' }}
      </p>
      <CompareSearch
        variant="wide"
        :placeholder="copy.compare.pickSecondPlaceholder"
        :exclude-slug="slugA ?? undefined"
        @select="onPickB"
      />
    </div>

    <div v-else-if="!slugA && slugB" class="space-y-4">
      <p class="text-fg-muted">
        … {{ copy.compare.versus }}
        <span class="font-semibold text-fg">{{ careerB?.first_name }} {{ careerB?.last_name }}</span>
      </p>
      <CompareSearch
        variant="wide"
        :placeholder="copy.compare.pickFirstPlaceholder"
        :exclude-slug="slugB ?? undefined"
        @select="onPickA"
      />
    </div>

    <!-- Both picked -->
    <template v-else>
      <p v-if="loading" class="text-fg-muted">{{ copy.compare.loading }}</p>
      <p v-else-if="error" class="text-accent-strong">{{ error }}</p>

      <template v-else-if="careerA && careerB && statsA && statsB">
        <!-- Stats cards -->
        <h2 class="text-sm uppercase tracking-[0.08em] text-fg-faint mb-3">
          {{ copy.compare.statsHeading }}
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
          <article class="rounded-lg border border-border bg-bg-elevated p-5">
            <header class="mb-3">
              <h3 class="text-lg font-bold">
                <a :href="`/rider/${encodeURIComponent(careerA.slug)}`" class="hover:text-accent">
                  {{ nameA() }}
                </a>
              </h3>
              <p class="text-xs text-fg-muted mt-1">{{ statsA.categoriesByYear }}</p>
            </header>
            <dl class="grid grid-cols-2 gap-y-1.5 text-sm">
              <dt class="text-fg-muted">{{ copy.compare.statSeasons }}</dt><dd class="text-right mono">{{ statsA.seasons }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statStarts }}</dt><dd class="text-right mono">{{ statsA.starts }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statFinishes }}</dt><dd class="text-right mono">{{ statsA.finishes }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statBestOverall }}</dt><dd class="text-right mono">{{ fmtBest(statsA.bestOverall) }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statTotalPoints }}</dt><dd class="text-right mono">{{ statsA.totalPoints }}</dd>
            </dl>
          </article>

          <article class="rounded-lg border border-border bg-bg-elevated p-5">
            <header class="mb-3">
              <h3 class="text-lg font-bold">
                <a :href="`/rider/${encodeURIComponent(careerB.slug)}`" class="hover:text-accent">
                  {{ nameB() }}
                </a>
              </h3>
              <p class="text-xs text-fg-muted mt-1">{{ statsB.categoriesByYear }}</p>
            </header>
            <dl class="grid grid-cols-2 gap-y-1.5 text-sm">
              <dt class="text-fg-muted">{{ copy.compare.statSeasons }}</dt><dd class="text-right mono">{{ statsB.seasons }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statStarts }}</dt><dd class="text-right mono">{{ statsB.starts }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statFinishes }}</dt><dd class="text-right mono">{{ statsB.finishes }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statBestOverall }}</dt><dd class="text-right mono">{{ fmtBest(statsB.bestOverall) }}</dd>
              <dt class="text-fg-muted">{{ copy.compare.statTotalPoints }}</dt><dd class="text-right mono">{{ statsB.totalPoints }}</dd>
            </dl>
          </article>
        </div>

        <!-- Head-to-head -->
        <header class="flex items-baseline justify-between mb-3">
          <h2 class="text-sm uppercase tracking-[0.08em] text-fg-faint">
            {{ copy.compare.headToHeadHeading }}
          </h2>
          <span v-if="h2hRows.length > 0" class="text-xs text-fg-muted">
            {{ copy.compare.headToHeadCount(h2hRows.length) }}
          </span>
        </header>

        <p v-if="h2hRows.length === 0" class="rounded-lg border border-border bg-bg-elevated p-6 text-fg-muted">
          {{ copy.compare.noShared }}
        </p>

        <div v-else class="overflow-x-auto rounded-lg border border-border">
          <table class="w-full text-sm">
            <thead class="bg-bg-muted text-xs uppercase tracking-[0.06em] text-fg-faint">
              <tr>
                <th class="px-3 py-2 text-left">{{ copy.compare.colRace }}</th>
                <th class="px-3 py-2 text-right">{{ careerA.last_name }}</th>
                <th class="px-3 py-2 text-right">{{ careerB.last_name }}</th>
                <th class="px-3 py-2 text-center">{{ copy.compare.colWinner }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in h2hRows" :key="row.key" class="border-t border-border hover:bg-bg-muted">
                <td class="px-3 py-2">
                  <a :href="raceLink(row)" class="hover:text-accent">
                    {{ row.eventName }} {{ row.year }}
                  </a>
                </td>
                <td class="px-3 py-2 text-right mono" :class="row.winner === 'a' ? 'text-accent-strong font-semibold' : ''">
                  {{ fmtPos(row.posA) }}
                </td>
                <td class="px-3 py-2 text-right mono" :class="row.winner === 'b' ? 'text-accent-strong font-semibold' : ''">
                  {{ fmtPos(row.posB) }}
                </td>
                <td class="px-3 py-2 text-center text-xs">
                  <span v-if="row.winner === 'a'">{{ careerA.last_name }}</span>
                  <span v-else-if="row.winner === 'b'">{{ careerB.last_name }}</span>
                  <span v-else class="text-fg-faint">{{ copy.compare.winnerTie }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="h2hRows.length > 0" class="mt-3 text-sm text-fg-muted">
          {{ copy.compare.summaryFmt(careerA.last_name, h2hSummary.a, careerB.last_name, h2hSummary.b, h2hSummary.tie) }}
        </p>
      </template>
    </template>
  </section>
</template>
