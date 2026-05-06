<script setup lang="ts">
// /races — race calendar with map (left) + list (right). Approved as
// variant C from the 2026-05-06 design-shotgun session. Reads ?season=
// from the URL, fetches that season's events, computes status against
// today, and renders pins + list with one entry expanded inline.
//
// Pin coordinates are hardcoded by slug (decorative map, not a real
// projection — see RACE_PIN_COORDS below). Slugs we don't recognize
// get a centered fallback pin so the page never breaks for new races.

import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue';
import type { EventListOut, EventRef, SeasonRef } from '~/lib/api.types';
import { copy } from '~/lib/copy';

// Build-time env var (Astro/Vite convention). When set, the page renders a
// real Google Map; when unset, falls back to the stylized SVG silhouette.
const GOOGLE_MAPS_API_KEY = (import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY ?? '').trim();
const USE_GOOGLE_MAPS = GOOGLE_MAPS_API_KEY.length > 0;

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

// Real-world coordinates for each race location. Used by the Google
// Maps view when the API key is configured. Decimal degrees, WGS84.
const RACE_LATLNG: Record<string, { lat: number; lng: number }> = {
  'buhovo':         { lat: 42.7833, lng: 23.5333 },
  'kyrnare':        { lat: 42.8242, lng: 24.7728 },
  'karnare':        { lat: 42.8242, lng: 24.7728 },
  'alba-damascena': { lat: 42.6167, lng: 25.4000 },
  'kornica':        { lat: 41.6042, lng: 23.7872 },
  'kornitsa':       { lat: 41.6042, lng: 23.7872 },
  'stara-zagora':   { lat: 42.4258, lng: 25.6342 },
  'kirkovo':        { lat: 41.3333, lng: 25.4167 },
  'hard_enduro-kirkovo': { lat: 41.3333, lng: 25.4167 },
  'bansko':         { lat: 41.8344, lng: 23.4856 },
  'gorna-malina':   { lat: 42.6667, lng: 23.7000 },
  'sopot':          { lat: 42.6533, lng: 24.7589 },
  'varna':          { lat: 43.2141, lng: 27.9147 },
  'botevgrad':      { lat: 42.9000, lng: 23.7833 },
  'sevtopolis':     { lat: 42.6167, lng: 25.4000 },
  'six_crazy_job':  { lat: 42.4258, lng: 25.6342 },
};

function resolveLatLng(slug: string): { lat: number; lng: number } | null {
  const norm = slug.toLowerCase().replace(/_/g, '-');
  if (RACE_LATLNG[norm]) return RACE_LATLNG[norm];
  for (const [key, ll] of Object.entries(RACE_LATLNG)) {
    if (norm.endsWith(key) || norm.includes(key)) return ll;
  }
  return null;  // unknown slug → no pin on the Google map
}

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

onBeforeUnmount(() => {
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
});

function changeYear(e: Event) {
  const year = Number((e.target as HTMLSelectElement).value);
  selectedYear.value = year;
  const u = new URL(window.location.href);
  u.searchParams.set('season', String(year));
  window.history.pushState({}, '', u.toString());
  void loadSeason(year);
}

// ---------------------------------------------------------------------------
// Google Maps integration (loaded only when PUBLIC_GOOGLE_MAPS_API_KEY is set)
// ---------------------------------------------------------------------------

const googleMapsContainer = ref<HTMLElement | null>(null);
const googleMapsFailed = ref(false);
let gmap: any = null;
let gmarkers: any[] = [];
let bulgariaPolygon: any = null;
let themeObserver: MutationObserver | null = null;

// Bulgaria outline — counter-clockwise from the NW (Bregovo/Vidin area),
// down the Serbian/Macedonian border, along the Greek/Turkish border,
// up the Black Sea coast, then west along the Danube back to the start.
// ~85 points; coordinates from a simplified version of Natural Earth's
// 1:50m country admin boundary. Accurate enough to read as Bulgaria at
// a glance, light enough to inline without bloating the JS bundle.
const BULGARIA_OUTLINE: Array<{ lat: number; lng: number }> = [
  // NW corner / Danube bend at Bregovo
  { lat: 44.21, lng: 22.66 }, { lat: 44.07, lng: 22.62 },
  // Western border (Serbia)
  { lat: 43.97, lng: 22.62 }, { lat: 43.81, lng: 22.40 },
  { lat: 43.68, lng: 22.49 }, { lat: 43.40, lng: 22.52 },
  { lat: 43.20, lng: 22.55 }, { lat: 43.04, lng: 22.66 },
  { lat: 42.92, lng: 22.51 }, { lat: 42.69, lng: 22.50 },
  // SW (Macedonia)
  { lat: 42.48, lng: 22.42 }, { lat: 42.32, lng: 22.41 },
  { lat: 42.23, lng: 22.46 }, { lat: 42.11, lng: 22.55 },
  { lat: 41.93, lng: 22.91 }, { lat: 41.85, lng: 22.93 },
  // S (Greek border, Pirin → Rhodope)
  { lat: 41.74, lng: 22.95 }, { lat: 41.51, lng: 22.96 },
  { lat: 41.40, lng: 23.04 }, { lat: 41.40, lng: 23.30 },
  { lat: 41.43, lng: 23.55 }, { lat: 41.43, lng: 23.78 },
  { lat: 41.40, lng: 24.08 }, { lat: 41.34, lng: 24.36 },
  { lat: 41.31, lng: 24.49 }, { lat: 41.34, lng: 24.71 },
  { lat: 41.30, lng: 24.95 }, { lat: 41.21, lng: 25.20 },
  { lat: 41.20, lng: 25.55 }, { lat: 41.30, lng: 25.79 },
  { lat: 41.31, lng: 26.00 }, { lat: 41.31, lng: 26.15 },
  // SE corner (Greece/Turkey)
  { lat: 41.39, lng: 26.30 }, { lat: 41.55, lng: 26.33 },
  { lat: 41.74, lng: 26.36 }, { lat: 41.95, lng: 26.71 },
  { lat: 42.05, lng: 27.05 }, { lat: 42.10, lng: 27.35 },
  // Black Sea coast (Tsarevo → Burgas → Varna → Kaliakra)
  { lat: 42.10, lng: 27.40 }, { lat: 42.30, lng: 27.55 },
  { lat: 42.42, lng: 27.61 }, { lat: 42.50, lng: 27.47 },
  { lat: 42.65, lng: 27.62 }, { lat: 42.80, lng: 27.81 },
  { lat: 43.05, lng: 27.91 }, { lat: 43.21, lng: 27.93 },
  { lat: 43.40, lng: 28.20 }, { lat: 43.61, lng: 28.50 },
  { lat: 43.74, lng: 28.58 },
  // NE / Romanian border (Cape Kaliakra → Silistra)
  { lat: 43.83, lng: 28.55 }, { lat: 43.97, lng: 28.50 },
  { lat: 43.99, lng: 28.40 }, { lat: 44.05, lng: 28.05 },
  { lat: 44.10, lng: 27.66 }, { lat: 44.12, lng: 27.27 },
  // N / Danube (Silistra → Ruse → Svishtov → Vidin)
  { lat: 44.07, lng: 26.95 }, { lat: 44.05, lng: 26.62 },
  { lat: 43.99, lng: 26.45 }, { lat: 43.97, lng: 26.21 },
  { lat: 43.92, lng: 26.05 }, { lat: 43.85, lng: 25.97 },
  { lat: 43.81, lng: 25.78 }, { lat: 43.78, lng: 25.74 },
  { lat: 43.69, lng: 25.55 }, { lat: 43.62, lng: 25.35 },
  { lat: 43.65, lng: 25.13 }, { lat: 43.71, lng: 24.90 },
  { lat: 43.74, lng: 24.65 }, { lat: 43.78, lng: 24.46 },
  { lat: 43.85, lng: 24.30 }, { lat: 43.94, lng: 24.06 },
  { lat: 43.97, lng: 23.92 }, { lat: 43.99, lng: 23.69 },
  { lat: 43.93, lng: 23.43 }, { lat: 43.85, lng: 23.27 },
  { lat: 43.88, lng: 23.05 }, { lat: 43.97, lng: 22.92 },
  { lat: 44.06, lng: 22.85 }, { lat: 44.10, lng: 22.79 },
  { lat: 44.13, lng: 22.71 }, { lat: 44.18, lng: 22.66 },
];

function loadGoogleMapsScript(): Promise<void> {
  // Idempotent — multiple .vue islands could mount at once; only inject once.
  return new Promise((resolve, reject) => {
    if ((window as any).google?.maps) return resolve();
    const existing = document.querySelector('script[data-bgx-gmaps]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('script load')), { once: true });
      return;
    }
    const s = document.createElement('script');
    s.async = true;
    s.defer = true;
    s.dataset.bgxGmaps = '1';
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(GOOGLE_MAPS_API_KEY)}&v=weekly&loading=async`;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('script load'));
    document.head.appendChild(s);
  });
}

// Style arrays for the legacy Map. New cloud-based styling would need
// a Map ID which we don't have; keeping these inline lets us swap on
// theme toggle without provisioning anything in Cloud Console.
const GMAP_DARK_STYLES = [
  { elementType: 'geometry', stylers: [{ color: '#0a0a0a' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0a0a0a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#737373' }] },
  { featureType: 'administrative.country', elementType: 'geometry.stroke', stylers: [{ color: '#262626' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#a3a3a3' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1a1a1a' }] },
  { featureType: 'road', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#141414' }] },
  { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#0f0f0f' }] },
];

const GMAP_LIGHT_STYLES = [
  { elementType: 'geometry', stylers: [{ color: '#fafafa' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#ffffff' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#737373' }] },
  { featureType: 'administrative.country', elementType: 'geometry.stroke', stylers: [{ color: '#d4d4d4' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#525252' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
  { featureType: 'road', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#e5e5e5' }] },
  { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#f5f5f5' }] },
];

function isDarkMode(): boolean {
  return typeof document !== 'undefined'
    && document.documentElement.classList.contains('dark');
}

function currentMapStyles() {
  return isDarkMode() ? GMAP_DARK_STYLES : GMAP_LIGHT_STYLES;
}

function currentAccentColor(): string {
  if (typeof window === 'undefined') return '#e65100';
  const v = getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim();
  return v || '#e65100';
}

function pinIcon(status: 'past' | 'next' | 'future' | 'tbd', selected: boolean) {
  const ACCENT = currentAccentColor();
  const isFilled = status === 'past' || status === 'next';
  // SVG circle marker. Selection adds a ring; "next" gets a halo.
  const fill = isFilled ? ACCENT : '#0a0a0a';
  const stroke = ACCENT;
  const strokeWidth = isFilled ? 1.5 : 2.5;
  const opacity = status === 'past' ? 0.6 : 1;
  const ring = selected ? `<circle cx="16" cy="16" r="14" fill="none" stroke="${ACCENT}" stroke-width="2" opacity="0.7"/>` : '';
  const halo = status === 'next' ? `<circle cx="16" cy="16" r="13" fill="${ACCENT}" opacity="0.25"/>` : '';
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      ${halo}${ring}
      <circle cx="16" cy="16" r="${status === 'next' ? 9 : 8}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}" opacity="${opacity}"/>
    </svg>
  `;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new (window as any).google.maps.Size(32, 32),
    anchor: new (window as any).google.maps.Point(16, 16),
  };
}

async function renderGoogleMap() {
  if (!USE_GOOGLE_MAPS) return;
  if (!googleMapsContainer.value || races.value.length === 0) return;
  try {
    await loadGoogleMapsScript();
    const g = (window as any).google;
    const dark = isDarkMode();
    const accent = currentAccentColor();
    if (!gmap) {
      gmap = new g.maps.Map(googleMapsContainer.value, {
        center: { lat: 42.7, lng: 25.5 },
        zoom: 7,
        styles: dark ? GMAP_DARK_STYLES : GMAP_LIGHT_STYLES,
        disableDefaultUI: true,
        zoomControl: true,
        gestureHandling: 'cooperative',
        backgroundColor: dark ? '#0a0a0a' : '#fafafa',
      });
      // Bulgaria outline drawn once with the current accent.
      bulgariaPolygon = new g.maps.Polygon({
        paths: BULGARIA_OUTLINE,
        strokeColor: accent,
        strokeOpacity: 0.65,
        strokeWeight: 2,
        fillColor: accent,
        fillOpacity: 0.05,
        clickable: false,
        zIndex: 0,
        map: gmap,
      });
      // Watch the host <html> class attribute so theme toggles re-style
      // the map without a page reload. Disconnected on unmount.
      if (typeof MutationObserver !== 'undefined' && !themeObserver) {
        themeObserver = new MutationObserver(() => applyMapTheme());
        themeObserver.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ['class'],
        });
      }
    }
    // Replace markers each render — race data + status can change with year.
    gmarkers.forEach(m => m.setMap(null));
    gmarkers = [];
    for (const r of races.value) {
      const ll = resolveLatLng(r.ev.slug);
      if (!ll) continue;
      const marker = new g.maps.Marker({
        position: ll,
        map: gmap,
        title: r.ev.name,
        icon: pinIcon(r.status, selectedSlug.value === r.ev.slug),
        zIndex: r.status === 'next' ? 1000 : (selectedSlug.value === r.ev.slug ? 800 : 100),
      });
      marker.addListener('click', () => pickRace(r.ev.slug));
      gmarkers.push(marker);
    }
  } catch (e) {
    googleMapsFailed.value = true;
  }
}

function applyMapTheme() {
  if (!gmap) return;
  const dark = isDarkMode();
  const accent = currentAccentColor();
  gmap.setOptions({
    styles: dark ? GMAP_DARK_STYLES : GMAP_LIGHT_STYLES,
    backgroundColor: dark ? '#0a0a0a' : '#fafafa',
  });
  if (bulgariaPolygon) {
    bulgariaPolygon.setOptions({ strokeColor: accent, fillColor: accent });
  }
  // Re-skin every marker so the SVG icon picks up the new accent.
  for (const m of gmarkers) {
    const slug = (m as any).getTitle?.();
    const r = races.value.find(x => x.ev.name === slug);
    if (!r) continue;
    m.setIcon(pinIcon(r.status, selectedSlug.value === r.ev.slug));
  }
}

watch([races, selectedSlug, googleMapsContainer], () => {
  if (USE_GOOGLE_MAPS && !googleMapsFailed.value) {
    void nextTick(renderGoogleMap);
  }
});
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
      <div class="relative h-[600px] rounded-2xl border border-border bg-bg-elevated overflow-hidden">
        <!-- Google Maps when key is configured and load succeeded -->
        <div
          v-if="USE_GOOGLE_MAPS && !googleMapsFailed"
          ref="googleMapsContainer"
          class="absolute inset-0"
        ></div>
        <!-- Fallback: stylized SVG silhouette (always present in DOM if no key, OR if Google failed) -->
        <div v-else class="relative w-full h-full p-7">
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
        </div>
        <!-- Legend, sits above whichever map renders. Pointer-events-none so
             it doesn't intercept Google Maps clicks/drags. -->
        <div class="absolute bottom-4 left-4 flex gap-3 text-[11px] uppercase tracking-[0.06em] text-fg-muted bg-bg-elevated/80 backdrop-blur px-3 py-1.5 rounded-md pointer-events-none">
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
