<script setup lang="ts">
// /races — race calendar with map (left) + list (right). Approved as
// variant C from the 2026-05-06 design-shotgun session. Reads ?season=
// from the URL, fetches that season's events, computes status against
// today, and renders pins + list with one entry expanded inline.
//
// Pin coordinates are hardcoded by slug (decorative map, not a real
// projection — see RACE_PIN_COORDS below). Slugs we don't recognize
// get a centered fallback pin so the page never breaks for new races.

import { computed, onMounted, ref } from 'vue';
import type { EventListOut, EventRef, SeasonRef } from '~/lib/api.types';
import { copy } from '~/lib/copy';

const props = defineProps<{
  defaultYear: number;
  allYears: number[];
}>();

interface RaceWithStatus {
  ev: EventRef;
  status: 'past' | 'next' | 'future' | 'tbd';
  daysFromToday: number | null;  // null when no event_date
  pin: { x: number; y: number; fallback: boolean };
}

const season = ref<SeasonRef | null>(null);
const races = ref<RaceWithStatus[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const selectedSlug = ref<string | null>(null);
const selectedYear = ref<number>(props.defaultYear);

// Approximate Bulgarian geography. SVG viewBox is 500x380. Slugs are
// normalized to lowercase + underscores → hyphens before lookup.
const RACE_PIN_COORDS: Record<string, { x: number; y: number }> = {
  'buhovo':         { x: 120, y: 170 },
  'kyrnare':        { x: 240, y: 190 },
  'karnare':        { x: 240, y: 190 },
  'alba-damascena': { x: 290, y: 210 },
  'kornica':        { x: 155, y: 265 },
  'kornitsa':       { x: 155, y: 265 },
  'stara-zagora':   { x: 320, y: 240 },
  'kirkovo':        { x: 380, y: 275 },
  'hard_enduro-kirkovo': { x: 380, y: 275 },
  'bansko':         { x: 165, y: 280 },
  'gorna-malina':   { x: 175, y: 175 },
  'sopot':          { x: 215, y: 195 },
  'varna':          { x: 425, y: 175 },
  'botevgrad':      { x: 175, y: 165 },
  'sevtopolis':     { x: 285, y: 215 },
  'six_crazy_job':  { x: 320, y: 240 },
};

function normalizeSlug(slug: string): string {
  return slug.toLowerCase().replace(/_/g, '-');
}

function resolvePin(slug: string): { x: number; y: number; fallback: boolean } {
  const norm = normalizeSlug(slug);
  // Try exact match first; then prefix match for slugs like
  // "hard_enduro-kirkovo" → "kirkovo".
  if (RACE_PIN_COORDS[norm]) return { ...RACE_PIN_COORDS[norm], fallback: false };
  for (const [key, coords] of Object.entries(RACE_PIN_COORDS)) {
    if (norm.endsWith(key) || norm.includes(key)) {
      return { ...coords, fallback: false };
    }
  }
  // Fallback: center of the map. Pin still renders so the race shows up.
  return { x: 250, y: 200, fallback: true };
}

function classifyRaces(events: EventRef[]): RaceWithStatus[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const items: RaceWithStatus[] = events.map(ev => {
    const pin = resolvePin(ev.slug);
    if (!ev.event_date) {
      return { ev, status: 'tbd', daysFromToday: null, pin };
    }
    const date = new Date(ev.event_date);
    date.setHours(0, 0, 0, 0);
    const days = Math.round((date.getTime() - today.getTime()) / 86400000);
    const status = days < 0 ? 'past' : 'future';
    return { ev, status, daysFromToday: days, pin };
  });
  // Promote the closest future race to "next".
  let nextIdx = -1;
  let smallest = Infinity;
  items.forEach((it, i) => {
    if (it.status === 'future' && it.daysFromToday != null && it.daysFromToday < smallest) {
      smallest = it.daysFromToday;
      nextIdx = i;
    }
  });
  if (nextIdx >= 0) items[nextIdx].status = 'next';
  return items;
}

async function loadSeason(year: number) {
  loading.value = true;
  error.value = null;
  try {
    const res = await fetch(`/api/seasons/${year}/events`);
    if (!res.ok) {
      error.value = copy.racesPage.empty(year);
      season.value = null;
      races.value = [];
      return;
    }
    const data = (await res.json()) as EventListOut;
    season.value = data.season;
    races.value = classifyRaces(data.events);
    // Default selection: the next upcoming race, or the first past race
    // if everything's done, or the first race if dates are TBD.
    const next = races.value.find(r => r.status === 'next');
    const last = [...races.value].reverse().find(r => r.status === 'past');
    selectedSlug.value = (next?.ev.slug ?? last?.ev.slug ?? races.value[0]?.ev.slug) ?? null;
  } finally {
    loading.value = false;
  }
}

const stats = computed(() => {
  const total = races.value.length;
  const completed = races.value.filter(r => r.status === 'past').length;
  const upcoming = races.value.filter(r => r.status === 'next' || r.status === 'future').length;
  return { total, completed, upcoming };
});

const selected = computed<RaceWithStatus | null>(() => {
  if (!selectedSlug.value) return null;
  return races.value.find(r => r.ev.slug === selectedSlug.value) ?? null;
});

function pickRace(slug: string) {
  selectedSlug.value = slug;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return copy.racesPage.statusTbd;
  const d = new Date(iso);
  const months = ['Яну', 'Фев', 'Мар', 'Апр', 'Май', 'Юни', 'Юли', 'Авг', 'Сеп', 'Окт', 'Ное', 'Дек'];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

function fmtDay(iso: string | null | undefined): string {
  if (!iso) return '—';
  return String(new Date(iso).getDate()).padStart(2, '0');
}

function fmtMonth(iso: string | null | undefined): string {
  if (!iso) return '—';
  const months = ['Яну', 'Фев', 'Мар', 'Апр', 'Май', 'Юни', 'Юли', 'Авг', 'Сеп', 'Окт', 'Ное', 'Дек'];
  return months[new Date(iso).getMonth()];
}

function leaderboardHref(slug: string, year: number): string {
  return `/results?season=${year}&race=${encodeURIComponent(slug)}`;
}

function detailHref(slug: string): string {
  return `/races/${encodeURIComponent(slug)}`;
}

onMounted(() => {
  // Read ?season= from URL; fall back to the build-time defaultYear.
  const u = new URL(window.location.href);
  const param = u.searchParams.get('season');
  if (param && /^\d{4}$/.test(param) && props.allYears.includes(Number(param))) {
    selectedYear.value = Number(param);
  } else {
    selectedYear.value = props.defaultYear;
  }
  void loadSeason(selectedYear.value);
});

function changeYear(e: Event) {
  const year = Number((e.target as HTMLSelectElement).value);
  selectedYear.value = year;
  const u = new URL(window.location.href);
  u.searchParams.set('season', String(year));
  window.history.pushState({}, '', u.toString());
  void loadSeason(year);
}
</script>

<template>
  <section class="mx-auto max-w-[1280px] px-4 py-8 md:py-10">
    <header class="flex flex-wrap items-baseline justify-between gap-3 mb-2">
      <h1 class="text-3xl md:text-[42px] font-extrabold tracking-[-0.02em] uppercase leading-[1]">
        {{ copy.racesPage.h1(selectedYear) }}
      </h1>
      <select
        :value="selectedYear"
        @change="changeYear"
        class="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
      >
        <option v-for="y in allYears" :key="y" :value="y">{{ y }}</option>
      </select>
    </header>
    <p class="text-fg-muted text-sm mb-8">
      {{ copy.racesPage.subtitleFmt(stats.total, stats.completed, stats.upcoming) }}
    </p>

    <p v-if="loading" class="text-fg-muted">{{ copy.common.loading }}</p>
    <p v-else-if="error" class="rounded-lg border border-border bg-bg-elevated p-6 text-fg-muted">{{ error }}</p>
    <p v-else-if="races.length === 0" class="rounded-lg border border-border bg-bg-elevated p-6 text-fg-muted">
      {{ copy.racesPage.empty(selectedYear) }}
    </p>

    <div v-else class="grid grid-cols-1 lg:grid-cols-[55fr_45fr] gap-7">
      <!-- Map -->
      <div class="relative h-[600px] rounded-2xl border border-border bg-bg-elevated p-7 overflow-hidden">
        <div class="absolute top-4 right-4 text-[11px] tracking-[0.1em] text-fg-faint flex items-center gap-1.5">↑ N</div>
        <svg viewBox="0 0 500 380" class="w-full h-full">
          <!-- Stylized Bulgaria silhouette -->
          <path
            d="M40 130 Q 80 90 130 95 Q 200 100 250 90 Q 320 85 380 100 Q 430 110 460 145 Q 470 200 440 240 Q 400 280 350 290 Q 290 300 240 290 Q 180 285 130 270 Q 80 250 50 220 Q 30 175 40 130 Z"
            fill="#1a1a1a"
            stroke="#2a2a2a"
            stroke-width="1.2"
          />
          <!-- Subtle terrain lines -->
          <path
            d="M80 180 Q 150 165 220 175 M180 220 Q 260 210 340 220 M120 240 Q 200 250 280 245"
            stroke="#222" stroke-width="0.8" fill="none"
          />
          <!-- Pins -->
          <g v-for="r in races" :key="r.ev.slug" class="cursor-pointer" @click="pickRace(r.ev.slug)">
            <!-- Pulse for the next race -->
            <circle
              v-if="r.status === 'next'"
              :cx="r.pin.x" :cy="r.pin.y" r="14"
              fill="rgba(230,81,0,0.35)"
              class="origin-center"
            >
              <animate attributeName="r" values="8;18;8" dur="2.2s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.55;0;0.55" dur="2.2s" repeatCount="indefinite"/>
            </circle>
            <!-- Outer ring on selection -->
            <circle
              v-if="selectedSlug === r.ev.slug"
              :cx="r.pin.x" :cy="r.pin.y" r="13"
              fill="none" stroke="var(--color-accent)" stroke-width="2"
              opacity="0.7"
            />
            <!-- Pin -->
            <circle
              :cx="r.pin.x" :cy="r.pin.y"
              :r="r.status === 'next' ? 9 : 8"
              :fill="r.status === 'past' || r.status === 'next' ? 'var(--color-accent)' : 'transparent'"
              :stroke="'var(--color-accent)'"
              :stroke-width="r.status === 'future' || r.status === 'tbd' ? 2.5 : 1.5"
              :opacity="r.status === 'past' ? 0.55 : 1"
              :stroke-dasharray="r.pin.fallback ? '3,2' : 'none'"
            />
            <!-- Label -->
            <text
              :x="r.pin.x" :y="r.pin.y - 14"
              text-anchor="middle"
              class="font-mono"
              :style="{
                fontSize: '10px',
                fill: r.status === 'next' ? 'var(--color-accent-strong)' : 'var(--color-fg-muted)',
                fontWeight: r.status === 'next' || selectedSlug === r.ev.slug ? 700 : 400,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }"
            >
              R{{ races.findIndex(x => x.ev.slug === r.ev.slug) + 1 }} {{ r.ev.name.replace(/\s\d+$/, '') }}
            </text>
          </g>
        </svg>
        <!-- Legend -->
        <div class="absolute bottom-4 left-4 flex gap-3 text-[11px] uppercase tracking-[0.06em] text-fg-muted">
          <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-accent"></span> {{ copy.racesPage.legendCompleted }}</span>
          <span class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-accent ring-2 ring-accent/30"></span> {{ copy.racesPage.legendNext }}
          </span>
          <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full border-2 border-accent"></span> {{ copy.racesPage.legendUpcoming }}</span>
        </div>
      </div>

      <!-- List -->
      <div class="flex flex-col gap-2.5">
        <template v-for="(r, i) in races" :key="r.ev.slug">
          <!-- Expanded card -->
          <article
            v-if="selectedSlug === r.ev.slug"
            class="rounded-xl border-2 border-accent bg-bg-elevated p-6 shadow-sm"
            :style="{ boxShadow: '0 0 0 4px var(--color-accent-soft)' }"
          >
            <div class="flex items-baseline gap-3 flex-wrap">
              <span class="font-mono text-sm font-bold text-accent-strong">R{{ i + 1 }}</span>
              <h2 class="font-display text-2xl md:text-[28px] font-extrabold uppercase tracking-[-0.01em] leading-[1.05]">
                {{ r.ev.name }}
              </h2>
            </div>
            <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg-muted">
              <span><b class="text-fg font-semibold">{{ copy.racesPage.dateLabel }}</b> {{ fmtDate(r.ev.event_date) }}</span>
              <span v-if="r.ev.location"><b class="text-fg font-semibold">{{ copy.racesPage.locationLabel }}</b> {{ r.ev.location }}</span>
              <span v-if="r.daysFromToday != null && r.status !== 'past'" class="text-accent-strong font-semibold">
                {{ copy.racesPage.daysUntilFmt(r.daysFromToday) }}
              </span>
              <span v-else-if="r.status === 'past'" class="text-fg-faint">
                {{ copy.racesPage.statusCompleted }}
              </span>
            </div>
            <p class="mt-3.5 text-sm text-fg-muted leading-relaxed">
              {{ r.ev.description || copy.racesPage.descriptionFallback }}
            </p>
            <a
              v-if="r.ev.facebook_event_url"
              :href="r.ev.facebook_event_url"
              target="_blank" rel="noopener"
              class="mt-4 flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-3 text-white text-sm font-bold uppercase tracking-[0.04em] hover:bg-accent-strong transition-colors"
            >
              📘 {{ copy.racesPage.fbEventCta }}
            </a>
            <a
              :href="leaderboardHref(r.ev.slug, selectedYear)"
              class="mt-2 flex items-center justify-center rounded-lg border border-border px-4 py-2.5 text-sm font-semibold hover:border-accent transition-colors"
            >
              {{ copy.racesPage.leaderboardCta }}
            </a>
            <a
              :href="detailHref(r.ev.slug)"
              class="mt-2 block text-center text-xs text-fg-muted hover:text-accent uppercase tracking-[0.06em]"
            >
              {{ copy.racesPage.fullPageCta }}
            </a>
          </article>

          <!-- Collapsed row -->
          <button
            v-else
            type="button"
            @click="pickRace(r.ev.slug)"
            class="text-left grid grid-cols-[64px_1fr_24px] gap-3.5 items-center px-4 py-3.5 rounded-xl border border-border bg-bg-elevated hover:border-accent transition-colors"
            :class="{ 'opacity-60': r.status === 'past' }"
          >
            <span class="text-center px-2 py-1 border-r border-border">
              <span class="block font-mono text-2xl font-extrabold leading-none">{{ fmtDay(r.ev.event_date) }}</span>
              <span class="block font-mono text-[10px] text-fg-muted uppercase tracking-[0.08em] mt-0.5">{{ fmtMonth(r.ev.event_date) }}</span>
            </span>
            <span>
              <span class="block font-display font-bold text-base uppercase tracking-[-0.01em] leading-tight">
                {{ r.ev.name }} <span class="text-fg-muted font-normal">· R{{ i + 1 }}</span>
              </span>
              <span v-if="r.ev.location" class="block text-xs text-fg-muted mt-1">{{ r.ev.location }}</span>
            </span>
            <span class="justify-self-end">
              <span
                class="block w-2.5 h-2.5 rounded-full"
                :class="{
                  'bg-accent': r.status === 'past' || r.status === 'next',
                  'border-2 border-accent': r.status === 'future' || r.status === 'tbd',
                }"
                :style="r.status === 'next' ? 'box-shadow: 0 0 0 3px var(--color-accent-soft)' : ''"
              ></span>
            </span>
          </button>
        </template>
      </div>
    </div>
  </section>
</template>
