<script setup lang="ts">
// Single-page results island — frontend-restructure.md §T4.
//
// State source of truth = URL query params (?season, ?category, ?race).
// Every selector change goes through history.pushState so back/forward
// + reload + share-link all restore the same view. No router lib —
// pushState + popstate is enough for one page.
//
// Param precedence on mount:
//   - season  → URL → defaultYear (latest from build)
//   - category → URL → first category in season's category list
//   - race     → URL only (absent = standings view)
// If any default was filled, replaceState (not pushState) so the back
// button doesn't have to step through "the page filling its own defaults."

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { api } from '~/lib/api';
import { copy } from '~/lib/copy';
import { formatTime } from '~/lib/format';
import type {
  CategoryRef,
  EventRef,
  SeasonDetailOut,
  SeasonRef,
  StandingsOut,
  EventResultsOut,
} from '~/lib/api.types';

const props = defineProps<{
  seasons: SeasonRef[];
  defaultYear: number;
}>();

const seasonYear = ref<number>(props.defaultYear);
const categoryCode = ref<string>('');
const raceSlug = ref<string | null>(null);

const seasonDetail = ref<SeasonDetailOut | null>(null);
const standings = ref<StandingsOut | null>(null);
const raceResults = ref<EventResultsOut | null>(null);

const loading = ref(true);
const errorMessage = ref<string | null>(null);

let abort: AbortController | null = null;

// ---------------------------------------------------------------------------
// URL <-> state
// ---------------------------------------------------------------------------

function readUrl(): { season: number | null; category: string | null; race: string | null } {
  const u = new URL(window.location.href);
  const seasonRaw = u.searchParams.get('season');
  const seasonNum = seasonRaw && /^\d{4}$/.test(seasonRaw) ? Number(seasonRaw) : null;
  return {
    season: seasonNum,
    category: u.searchParams.get('category'),
    race: u.searchParams.get('race'),
  };
}

function buildUrl(state: { season: number; category: string; race: string | null }): string {
  const u = new URL(window.location.href);
  u.search = '';
  u.searchParams.set('season', String(state.season));
  u.searchParams.set('category', state.category);
  if (state.race) u.searchParams.set('race', state.race);
  return u.pathname + u.search;
}

function pushUrl(replace = false) {
  const url = buildUrl({
    season: seasonYear.value,
    category: categoryCode.value,
    race: raceSlug.value,
  });
  const fn = replace ? 'replaceState' : 'pushState';
  history[fn]({}, '', url);
}

// ---------------------------------------------------------------------------
// Data loaders
// ---------------------------------------------------------------------------

async function loadSeasonDetail(year: number): Promise<SeasonDetailOut> {
  return api.getSeason(year);
}

async function loadStandings(year: number, cat: string) {
  return api.getLeaderboard(year, cat);
}

async function loadRaceResults(year: number, cat: string, slug: string) {
  return api.getRaceResults(year, cat, slug);
}

async function refresh() {
  if (abort) abort.abort();
  abort = new AbortController();
  loading.value = true;
  errorMessage.value = null;

  try {
    if (!seasonDetail.value || seasonDetail.value.season.year !== seasonYear.value) {
      seasonDetail.value = await loadSeasonDetail(seasonYear.value);
    }
    // Resolve category against this season — if the URL/sticky value isn't a
    // valid code in the season, fall back to the first one.
    const validCodes = seasonDetail.value.categories.map(c => c.code);
    if (!validCodes.includes(categoryCode.value)) {
      categoryCode.value = validCodes[0] ?? '';
      pushUrl(true);
    }
    // Same for race: if ?race doesn't exist in this season, drop it.
    if (raceSlug.value) {
      const validSlugs = seasonDetail.value.events.map(e => e.slug);
      if (!validSlugs.includes(raceSlug.value)) {
        raceSlug.value = null;
        pushUrl(true);
      }
    }

    if (raceSlug.value) {
      raceResults.value = await loadRaceResults(seasonYear.value, categoryCode.value, raceSlug.value);
      standings.value = null;
    } else {
      standings.value = await loadStandings(seasonYear.value, categoryCode.value);
      raceResults.value = null;
    }
    // Visit tracking — fires once the resolved state is known. The
    // BaseLayout's inline tracker is suppressed via skipTracking, so this
    // is the authoritative track event for /results. Deduped per
    // (season, category, race) tuple to avoid double-counting when the
    // user toggles between equivalent filter states.
    trackCurrentState();
  } catch (err: any) {
    if (err?.name === 'AbortError') return;
    errorMessage.value = (err?.message as string) ?? 'unknown error';
  } finally {
    loading.value = false;
  }
}

let lastTracked: string | null = null;
function trackCurrentState() {
  const key = `${seasonYear.value}|${categoryCode.value}|${raceSlug.value ?? ''}`;
  if (key === lastTracked) return;
  lastTracked = key;
  const payload = raceSlug.value
    ? {
        page: 'race',
        category: categoryCode.value || null,
        season_year: seasonYear.value,
        event_slug: raceSlug.value,
        rider_slug: null,
      }
    : {
        page: 'leaderboard',
        category: categoryCode.value || null,
        season_year: seasonYear.value,
        event_slug: null,
        rider_slug: null,
      };
  try {
    fetch('/api/track', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => { /* fire-and-forget */ });
  } catch { /* never break the page for analytics */ }
}

// ---------------------------------------------------------------------------
// Mount + popstate wiring
// ---------------------------------------------------------------------------

function applyUrlToState(): { defaulted: boolean } {
  const url = readUrl();
  let defaulted = false;
  seasonYear.value = url.season ?? props.defaultYear;
  if (url.season == null) defaulted = true;
  // Category: keep URL value optimistically; refresh() will validate it.
  categoryCode.value = url.category ?? '';
  if (url.category == null) defaulted = true;
  raceSlug.value = url.race;
  return { defaulted };
}

function onPopState() {
  const { defaulted: _ } = applyUrlToState();
  refresh();
}

onMounted(async () => {
  const { defaulted } = applyUrlToState();
  await refresh();
  if (defaulted) pushUrl(true);
  window.addEventListener('popstate', onPopState);
});

onBeforeUnmount(() => {
  window.removeEventListener('popstate', onPopState);
  if (abort) abort.abort();
});

// ---------------------------------------------------------------------------
// User actions
// ---------------------------------------------------------------------------

function selectSeason(year: number) {
  if (year === seasonYear.value) return;
  seasonYear.value = year;
  // Drop ?race when switching seasons (race slug is season-specific).
  raceSlug.value = null;
  // Force re-resolve of category against the new season.
  seasonDetail.value = null;
  pushUrl(false);
  refresh();
}

function selectCategory(code: string) {
  if (code === categoryCode.value) return;
  categoryCode.value = code;
  pushUrl(false);
  refresh();
}

function selectRace(slug: string | null) {
  if (slug === raceSlug.value) return;
  raceSlug.value = slug;
  pushUrl(false);
  refresh();
}

// ---------------------------------------------------------------------------
// Derived helpers for the template
// ---------------------------------------------------------------------------

const events = computed<EventRef[]>(() => seasonDetail.value?.events ?? []);
const categories = computed<CategoryRef[]>(() => seasonDetail.value?.categories ?? []);
const activeRace = computed<EventRef | null>(() => {
  if (!raceSlug.value) return null;
  return events.value.find(e => e.slug === raceSlug.value) ?? null;
});
const activeCategory = computed<CategoryRef | null>(
  () => categories.value.find(c => c.code === categoryCode.value) ?? null,
);
const round = computed<number>(() => {
  if (!activeRace.value) return 0;
  return events.value.findIndex(e => e.slug === activeRace.value!.slug) + 1;
});

const isMultiDay = computed<boolean>(() => (raceResults.value?.days?.length ?? 1) > 1);

const standingsHasDropped = computed(
  () => standings.value?.championship_format === 'aggregate_2025',
);

function fmtPoints(n: number | null | undefined): string {
  if (n == null) return '—';
  return n % 1 === 0 ? String(n) : n.toFixed(1);
}

function urlForRace(slug: string | null): string {
  return buildUrl({
    season: seasonYear.value,
    category: categoryCode.value,
    race: slug,
  });
}

function urlForCategory(code: string): string {
  return buildUrl({
    season: seasonYear.value,
    category: code,
    race: raceSlug.value,
  });
}
</script>

<template>
  <div>
    <!-- Season picker -->
    <section class="mb-6 flex items-center gap-3 text-sm">
      <label for="season-select" class="text-fg-muted">{{ copy.results.seasonLabel }}</label>
      <select
        id="season-select"
        :value="seasonYear"
        @change="selectSeason(Number(($event.target as HTMLSelectElement).value))"
        class="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm font-semibold focus:border-accent focus:outline-none"
        :aria-label="copy.results.seasonAria"
      >
        <option v-for="s in props.seasons" :key="s.year" :value="s.year">
          {{ s.year }}{{ s.is_current ? ' ★' : '' }}
        </option>
      </select>
    </section>

    <!-- Category tabs -->
    <nav v-if="categories.length > 0" class="mb-4 flex flex-wrap gap-1 rounded-pill border border-border bg-bg-muted p-1">
      <a
        v-for="c in categories"
        :key="c.code"
        :href="urlForCategory(c.code)"
        @click.prevent="selectCategory(c.code)"
        :class="[
          'rounded-pill px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] transition-colors',
          c.code === categoryCode
            ? 'bg-accent text-white'
            : 'text-fg-muted hover:text-fg',
        ]"
      >
        {{ c.display_name }}
      </a>
    </nav>

    <!-- Race buttons (general + each event) -->
    <nav v-if="events.length > 0" class="mb-6 flex flex-wrap gap-2 text-sm">
      <a
        :href="urlForRace(null)"
        @click.prevent="selectRace(null)"
        :class="[
          'rounded-md border px-3 py-1.5 font-semibold uppercase tracking-[0.04em] transition-colors',
          raceSlug == null
            ? 'border-accent bg-accent-soft text-accent-strong'
            : 'border-border bg-bg-elevated text-fg-muted hover:border-accent hover:text-fg',
        ]"
      >
        ★ {{ copy.results.generalTab }}
      </a>
      <a
        v-for="(ev, i) in events"
        :key="ev.slug"
        :href="urlForRace(ev.slug)"
        @click.prevent="selectRace(ev.slug)"
        :class="[
          'rounded-md border px-3 py-1.5 transition-colors',
          ev.slug === raceSlug
            ? 'border-accent bg-accent-soft text-accent-strong font-semibold'
            : 'border-border bg-bg-elevated text-fg-muted hover:border-accent hover:text-fg',
        ]"
      >
        <span class="mono mr-2 text-xs text-fg-faint">R{{ i + 1 }}</span>
        <span>{{ ev.name }}</span>
      </a>
    </nav>

    <!-- Heading -->
    <header class="mb-4">
      <h1 v-if="raceSlug && activeRace && activeCategory" class="text-2xl md:text-[28px] font-extrabold tracking-[-0.02em]">
        {{ copy.results.raceH1(round, activeRace.name, activeCategory.display_name) }}
      </h1>
      <h1 v-else-if="activeCategory" class="text-2xl md:text-[28px] font-extrabold tracking-[-0.02em]">
        {{ copy.results.leaderboardH1(seasonYear, activeCategory.display_name) }}
      </h1>
    </header>

    <!-- Loading + error -->
    <div v-if="loading && !errorMessage" class="rounded-xl border border-border bg-bg-elevated p-8 text-center text-fg-muted">
      {{ copy.results.loading }}
    </div>
    <div v-else-if="errorMessage" class="rounded-xl border border-border bg-bg-elevated p-6">
      <h2 class="text-lg font-bold">{{ copy.results.errorTitle }}</h2>
      <p class="mt-2 text-sm text-fg-muted">{{ copy.results.errorBody }}</p>
      <p class="mt-1 text-xs text-fg-faint break-all">{{ errorMessage }}</p>
      <button
        @click="refresh()"
        class="mt-4 rounded-md border border-border bg-bg-muted px-4 py-2 text-sm font-semibold hover:border-accent"
      >
        {{ copy.results.errorRetry }}
      </button>
    </div>

    <!-- Race results table -->
    <div
      v-else-if="raceSlug && raceResults"
      class="card overflow-hidden rounded-xl border border-border bg-bg-elevated"
    >
      <div v-if="raceResults.rows.length === 0" class="p-8 text-center text-fg-muted">
        {{ copy.results.emptyRace }}
      </div>
      <div v-else class="scrollx">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colHash }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colNumber }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.results.colRider }}</th>
              <template v-if="isMultiDay">
                <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colDay1 }}</th>
                <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colDay2 }}</th>
                <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colCombinedTotal }}</th>
              </template>
              <th v-else class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colTime }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colPoints }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in raceResults.rows" :key="r.rider.race_number + '-' + r.rider.slug" class="hover:bg-[rgba(245,158,11,0.03)] border-b border-border-muted">
              <td class="px-3 py-3.5 text-center">
                <span v-if="r.position == null" class="text-fg-faint text-[11px]">DNF</span>
                <span v-else class="inline-flex h-7 min-w-[28px] items-center justify-center rounded-md bg-bg-muted px-2 font-bold text-[13px]">{{ r.position }}</span>
              </td>
              <td class="px-3 py-3.5 text-center">
                <a :href="`/rider/${encodeURIComponent(r.rider.slug)}`" class="mono hover:text-accent">{{ r.rider.race_number }}</a>
              </td>
              <td class="px-3 py-3.5">
                <a :href="`/rider/${encodeURIComponent(r.rider.slug)}`" class="hover:text-accent">
                  <span class="font-semibold">{{ r.rider.first_name }} {{ r.rider.last_name }}</span>
                  <span v-if="r.rider.team" class="ml-2 text-xs text-fg-muted">{{ r.rider.team }}</span>
                </a>
              </td>
              <template v-if="isMultiDay">
                <td class="px-3 py-3.5 text-right mono" :class="{ 'text-fg-faint': r.day_1_time_ms == null }">{{ r.day_1_time_ms != null ? formatTime(r.day_1_time_ms) : (r.day_1_status || '—') }}</td>
                <td class="px-3 py-3.5 text-right mono" :class="{ 'text-fg-faint': r.day_2_time_ms == null }">{{ r.day_2_time_ms != null ? formatTime(r.day_2_time_ms) : (r.day_2_status || '—') }}</td>
                <td class="px-3 py-3.5 text-right mono font-semibold">{{ formatTime(r.time_ms) }}</td>
              </template>
              <td v-else class="px-3 py-3.5 text-right mono">{{ formatTime(r.time_ms) }}</td>
              <td class="px-3 py-3.5 text-right">
                <span class="inline-block rounded-pill bg-accent-soft px-2.5 py-0.5 text-xs font-semibold text-accent-strong">
                  {{ fmtPoints(r.points) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Standings table -->
    <div
      v-else-if="standings"
      class="card overflow-hidden rounded-xl border border-border bg-bg-elevated"
    >
      <div v-if="standings.rows.length === 0" class="p-8 text-center text-fg-muted">
        {{ copy.results.emptyStandings(activeCategory?.display_name ?? '') }}
      </div>
      <div v-else class="scrollx">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colHash }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colNumber }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.results.colRider }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.results.colTotal }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colRaced }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.results.colBest }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in standings.rows" :key="row.rider.race_number + '-' + row.rider.slug" class="hover:bg-[rgba(245,158,11,0.03)] border-b border-border-muted">
              <td class="px-3 py-3.5 text-center">
                <span class="inline-flex h-7 min-w-[28px] items-center justify-center rounded-md bg-bg-muted px-2 font-bold text-[13px]">{{ row.final_position }}</span>
              </td>
              <td class="px-3 py-3.5 text-center">
                <a :href="`/rider/${encodeURIComponent(row.rider.slug)}`" class="mono hover:text-accent">{{ row.rider.race_number }}</a>
              </td>
              <td class="px-3 py-3.5">
                <a :href="`/rider/${encodeURIComponent(row.rider.slug)}`" class="hover:text-accent">
                  <span class="font-semibold">{{ row.rider.first_name }} {{ row.rider.last_name }}</span>
                  <span v-if="row.rider.team" class="ml-2 text-xs text-fg-muted">{{ row.rider.team }}</span>
                </a>
              </td>
              <td class="px-3 py-3.5 text-right mono font-semibold">{{ fmtPoints(row.total_points) }}</td>
              <td class="px-3 py-3.5 text-center">{{ row.races_participated }}</td>
              <td class="px-3 py-3.5 text-center">{{ row.best_position ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
