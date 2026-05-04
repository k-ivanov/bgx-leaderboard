<script setup lang="ts">
// Auth-gated stats island. Renders nothing in the static HTML — fetches
// /api/stats from the browser and either renders the dashboard or pops an
// inline login form when the API returns 401. Credentials are kept in
// sessionStorage so they vanish when the tab closes.
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { StatsOut } from '~/lib/api.types';
import { copy } from '~/lib/copy';

const STORAGE_KEY = 'bgx_stats_auth';
const REFRESH_MS = 60_000;

const stats = ref<StatsOut | null>(null);
const loading = ref(true);
const needsAuth = ref(false);
const authError = ref(false);
const username = ref('admin');
const password = ref('');
const submitting = ref(false);
const lastUpdated = ref<Date | null>(null);

let refreshTimer: ReturnType<typeof setInterval> | null = null;

function authHeader(): Record<string, string> {
  const v = sessionStorage.getItem(STORAGE_KEY);
  return v ? { Authorization: 'Basic ' + v } : {};
}

async function load(opts: { silent?: boolean } = {}) {
  // `silent` skips the loading flag — used by the auto-refresh timer so the
  // UI doesn't flash a "Зареждане…" placeholder every 60s.
  if (!opts.silent) loading.value = true;
  authError.value = false;
  try {
    const res = await fetch('/api/stats', {
      headers: { ...authHeader() },
    });
    if (res.status === 401) {
      sessionStorage.removeItem(STORAGE_KEY);
      needsAuth.value = true;
      stats.value = null;
      stopAutoRefresh();
      return;
    }
    if (!res.ok) {
      stats.value = null;
      needsAuth.value = false;
      return;
    }
    stats.value = (await res.json()) as StatsOut;
    lastUpdated.value = new Date();
    needsAuth.value = false;
    startAutoRefresh();
  } finally {
    if (!opts.silent) loading.value = false;
  }
}

function startAutoRefresh() {
  if (refreshTimer != null) return;
  refreshTimer = setInterval(() => {
    void load({ silent: true });
  }, REFRESH_MS);
}

function stopAutoRefresh() {
  if (refreshTimer != null) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function formatLastUpdated(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

async function submitLogin() {
  if (submitting.value) return;
  submitting.value = true;
  authError.value = false;
  try {
    const token = btoa(`${username.value}:${password.value}`);
    const res = await fetch('/api/stats', {
      headers: { Authorization: 'Basic ' + token },
    });
    if (res.status === 401) {
      authError.value = true;
      return;
    }
    if (!res.ok) {
      authError.value = true;
      return;
    }
    sessionStorage.setItem(STORAGE_KEY, token);
    stats.value = (await res.json()) as StatsOut;
    needsAuth.value = false;
    password.value = '';
  } finally {
    submitting.value = false;
  }
}

function logout() {
  sessionStorage.removeItem(STORAGE_KEY);
  stats.value = null;
  needsAuth.value = true;
  stopAutoRefresh();
}

function formatAvgSession(seconds: number): string {
  return seconds >= 60
    ? `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
    : `${Math.round(seconds)}s`;
}

function deviceCount(s: StatsOut, type: string): number {
  return s.devices.find((d) => d.device_type === type)?.count ?? 0;
}

function recentTimestamp(iso: string): string {
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 16);
}

function riderHref(yr: number | null | undefined, slug: string): string | null {
  if (yr == null) return null;
  const parts = slug.split('-');
  const raceNum = Number(parts[0]);
  const tail = parts.slice(1).join('-');
  if (Number.isNaN(raceNum) || !tail) return null;
  return `/${yr}/r/${raceNum}/${encodeURIComponent(tail)}`;
}

onMounted(() => {
  void load();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});
</script>

<template>
  <!-- Auth gate -->
  <section
    v-if="needsAuth"
    class="mx-auto max-w-md rounded-xl border border-border bg-bg-elevated p-6"
  >
    <h2 class="text-lg font-bold tracking-[-0.01em]">{{ copy.stats.authTitle }}</h2>
    <p class="mt-1 text-[14px] text-fg-muted">{{ copy.stats.authIntro }}</p>
    <form class="mt-4 space-y-3" @submit.prevent="submitLogin">
      <label class="block">
        <span class="block text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.authUsername }}
        </span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          class="mt-1 w-full rounded-md border border-border bg-bg-base px-3 py-2 text-[14px] focus:border-accent focus:outline-none"
        />
      </label>
      <label class="block">
        <span class="block text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.authPassword }}
        </span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="mt-1 w-full rounded-md border border-border bg-bg-base px-3 py-2 text-[14px] focus:border-accent focus:outline-none"
        />
      </label>
      <p v-if="authError" class="text-[13px] text-danger">{{ copy.stats.authError }}</p>
      <button
        type="submit"
        :disabled="submitting"
        class="w-full rounded-md bg-accent px-4 py-2 text-[14px] font-semibold text-bg-base transition-colors hover:bg-accent-strong disabled:opacity-60"
      >
        {{ copy.stats.authSubmit }}
      </button>
    </form>
  </section>

  <!-- Loading -->
  <p v-else-if="loading" class="text-[14px] text-fg-muted">{{ copy.stats.loading }}</p>

  <!-- Unavailable -->
  <p v-else-if="!stats" class="rounded-xl border border-border bg-bg-elevated p-4 text-[14px] text-fg-muted">
    {{ copy.stats.unavailable }}
  </p>

  <!-- Dashboard -->
  <template v-else>
    <div class="mb-6 flex items-center justify-end gap-4 text-[12px] uppercase tracking-[0.06em] text-fg-faint">
      <span v-if="lastUpdated" class="mono">
        {{ copy.stats.lastUpdated }}: {{ formatLastUpdated(lastUpdated) }}
      </span>
      <button
        type="button"
        class="font-semibold hover:text-accent"
        @click="logout"
      >
        {{ copy.stats.authLogout }}
      </button>
    </div>

    <section class="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statVisits }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ stats.total_visits }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statDesktop }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ deviceCount(stats, 'desktop') }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statMobile }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ deviceCount(stats, 'mobile') }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statUnknown }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ deviceCount(stats, 'unknown') }}</div>
      </div>
    </section>

    <section class="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statUniqueToday }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ stats.unique_visitors_today }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statSessionsToday }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ stats.sessions_today }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statAvgSession }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ formatAvgSession(stats.avg_session_seconds) }}</div>
      </div>
    </section>

    <section class="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statUnique7d }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ stats.unique_visitors_7d }}</div>
      </div>
      <div class="rounded-xl border border-border bg-bg-elevated p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-faint">
          {{ copy.stats.statUnique30d }}
        </div>
        <div class="mt-1 text-2xl font-extrabold mono">{{ stats.unique_visitors_30d }}</div>
      </div>
    </section>

    <section class="mb-10">
      <h2 class="mb-3 text-lg font-bold tracking-[-0.01em]">{{ copy.stats.sectionByCategory }}</h2>
      <p v-if="stats.per_category.length === 0" class="rounded-xl border border-border bg-bg-elevated p-4 text-[14px] text-fg-muted">
        {{ copy.stats.empty }}
      </p>
      <div v-else class="card overflow-hidden rounded-xl border border-border bg-bg-elevated">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colCategory }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.stats.colSeason }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.stats.colVisits }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(c, i) in stats.per_category" :key="`cat-${i}`" class="border-b border-border-muted">
              <td class="px-3 py-3">{{ c.category ?? '—' }}</td>
              <td class="px-3 py-3 text-center mono">{{ c.season_year ?? '—' }}</td>
              <td class="px-3 py-3 text-right mono">{{ c.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="mb-10">
      <h2 class="mb-3 text-lg font-bold tracking-[-0.01em]">{{ copy.stats.sectionByRace }}</h2>
      <p v-if="stats.per_race.length === 0" class="rounded-xl border border-border bg-bg-elevated p-4 text-[14px] text-fg-muted">
        {{ copy.stats.empty }}
      </p>
      <div v-else class="card overflow-hidden rounded-xl border border-border bg-bg-elevated">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colRace }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.stats.colSeason }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.stats.colVisits }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in stats.per_race" :key="`race-${i}`" class="border-b border-border-muted">
              <td class="px-3 py-3">
                <a v-if="r.season_year != null" class="hover:text-accent" :href="`/${r.season_year}/events/${r.event_slug}`">{{ r.event_slug }}</a>
                <template v-else>{{ r.event_slug }}</template>
              </td>
              <td class="px-3 py-3 text-center mono">{{ r.season_year ?? '—' }}</td>
              <td class="px-3 py-3 text-right mono">{{ r.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="mb-10">
      <h2 class="mb-3 text-lg font-bold tracking-[-0.01em]">{{ copy.stats.sectionByRider }}</h2>
      <p v-if="stats.per_rider.length === 0" class="rounded-xl border border-border bg-bg-elevated p-4 text-[14px] text-fg-muted">
        {{ copy.stats.empty }}
      </p>
      <div v-else class="card overflow-hidden rounded-xl border border-border bg-bg-elevated">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colRider }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.stats.colSeason }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.stats.colVisits }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in stats.per_rider" :key="`rider-${i}`" class="border-b border-border-muted">
              <td class="px-3 py-3">
                <a v-if="riderHref(r.season_year, r.rider_slug)" class="hover:text-accent" :href="riderHref(r.season_year, r.rider_slug) ?? undefined">
                  {{ r.rider_slug }}
                </a>
                <template v-else>{{ r.rider_slug }}</template>
              </td>
              <td class="px-3 py-3 text-center mono">{{ r.season_year ?? '—' }}</td>
              <td class="px-3 py-3 text-right mono">{{ r.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="mb-10">
      <h2 class="mb-3 text-lg font-bold tracking-[-0.01em]">{{ copy.stats.sectionComparisons }}</h2>
      <p v-if="stats.top_comparisons.length === 0" class="rounded-xl border border-border bg-bg-elevated p-4 text-[14px] text-fg-muted">
        {{ copy.stats.emptyComparisons }}
      </p>
      <div v-else class="card overflow-hidden rounded-xl border border-border bg-bg-elevated">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colRiderA }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colRiderB }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-right border-b border-border">{{ copy.stats.colVisits }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(c, i) in stats.top_comparisons" :key="`cmp-${i}`" class="border-b border-border-muted">
              <td class="px-3 py-3">
                <a class="hover:text-accent" :href="`/rider/${encodeURIComponent(c.slug_a)}`">{{ c.slug_a }}</a>
              </td>
              <td class="px-3 py-3">
                <a class="hover:text-accent" :href="`/rider/${encodeURIComponent(c.slug_b)}`">{{ c.slug_b }}</a>
              </td>
              <td class="px-3 py-3 text-right mono">{{ c.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 class="mb-3 text-lg font-bold tracking-[-0.01em]">{{ copy.stats.sectionRecent }}</h2>
      <div class="card overflow-hidden rounded-xl border border-border bg-bg-elevated">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-bg-muted">
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colTime }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colPage }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-left border-b border-border">{{ copy.stats.colCategory }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.stats.colSeason }}</th>
              <th class="text-fg-faint text-[11px] font-semibold uppercase tracking-[0.06em] px-3 py-3 text-center border-b border-border">{{ copy.stats.colDevice }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(v, i) in stats.recent" :key="`r-${i}`" class="border-b border-border-muted">
              <td class="px-3 py-3 mono">{{ recentTimestamp(v.timestamp) }}</td>
              <td class="px-3 py-3">{{ v.page }}</td>
              <td class="px-3 py-3">{{ v.category ?? '—' }}</td>
              <td class="px-3 py-3 text-center mono">{{ v.season_year ?? '—' }}</td>
              <td class="px-3 py-3 text-center">{{ v.device_type }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>
