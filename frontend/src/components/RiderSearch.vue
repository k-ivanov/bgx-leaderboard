<script setup lang="ts">
// Rider search island for the top nav.
//
// Debounced /api/riders/search call (cross-season — finds riders
// regardless of the season currently selected on /results). Dropdown
// overlay, arrow-key navigation, Enter to navigate, Esc to close. Each
// result links to /rider/{slug}, which is multi-season by design.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { GlobalRiderSearchOut, RiderSearchResultOut } from '~/lib/api.types';
import { copy } from '~/lib/copy';

defineProps<{
  defaultYear: number;
}>();

const query = ref('');
const results = ref<RiderSearchResultOut[]>([]);
const open = ref(false);
const loading = ref(false);
const cursor = ref(-1);

let debounceHandle: ReturnType<typeof setTimeout> | null = null;
let abortController: AbortController | null = null;

function clear() {
  query.value = '';
  results.value = [];
  cursor.value = -1;
  open.value = false;
}

async function runSearch(q: string) {
  if (abortController) abortController.abort();
  if (!q.trim()) {
    results.value = [];
    open.value = false;
    return;
  }
  abortController = new AbortController();
  loading.value = true;
  try {
    const url = `/api/riders/search?q=${encodeURIComponent(q)}&limit=10`;
    const res = await fetch(url, { signal: abortController.signal });
    if (!res.ok) {
      results.value = [];
      return;
    }
    const data = (await res.json()) as GlobalRiderSearchOut;
    results.value = data.results;
    open.value = true;
    cursor.value = data.results.length > 0 ? 0 : -1;
  } catch (e) {
    if ((e as Error).name !== 'AbortError') {
      results.value = [];
    }
  } finally {
    loading.value = false;
  }
}

function onInput(e: Event) {
  const v = (e.target as HTMLInputElement).value;
  query.value = v;
  if (debounceHandle) clearTimeout(debounceHandle);
  debounceHandle = setTimeout(() => runSearch(v), 250);
}

function navigateTo(r: RiderSearchResultOut) {
  // The slug is the cross-season rider identifier; year + race_number
  // are dropped here (rider profile owns its own meta).
  window.location.href = `/rider/${encodeURIComponent(r.rider.slug)}`;
}

function onKeydown(e: KeyboardEvent) {
  if (!open.value) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    cursor.value = Math.min(cursor.value + 1, results.value.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    cursor.value = Math.max(cursor.value - 1, 0);
  } else if (e.key === 'Enter') {
    if (cursor.value >= 0 && results.value[cursor.value]) {
      e.preventDefault();
      navigateTo(results.value[cursor.value]);
    }
  } else if (e.key === 'Escape') {
    clear();
  }
}

function onBlur() {
  // Delay so click on a result has a chance to fire.
  setTimeout(() => {
    open.value = false;
  }, 120);
}

const showEmpty = computed(
  () => open.value && !loading.value && query.value.trim().length > 0 && results.value.length === 0,
);

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  if (abortController) abortController.abort();
});
</script>

<template>
  <div class="relative">
    <input
      type="search"
      :placeholder="copy.search.placeholder"
      :value="query"
      @input="onInput"
      @focus="open = results.length > 0"
      @blur="onBlur"
      class="w-44 sm:w-56 rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-[13px] focus:border-accent focus:outline-none"
      autocomplete="off"
      :aria-label="copy.search.aria"
    />

    <div
      v-if="open && (results.length > 0 || showEmpty)"
      class="absolute mt-1 z-30 rounded-md border border-border bg-bg-elevated shadow-lg
             left-0 w-[calc(100vw-2rem)] max-w-[20rem]
             sm:left-auto sm:right-0 sm:w-72 sm:max-w-none"
    >
      <ul v-if="results.length > 0" class="max-h-80 overflow-y-auto">
        <li
          v-for="(r, i) in results"
          :key="`${r.season_year}-${r.rider.race_number}-${r.rider.slug}`"
          @mousedown="navigateTo(r)"
          @mouseenter="cursor = i"
          :class="[
            'flex items-baseline justify-between gap-3 px-3 py-2 cursor-pointer',
            i === cursor ? 'bg-bg-muted' : 'hover:bg-bg-muted',
          ]"
        >
          <span class="text-[13px]">
            <span class="mono text-fg-muted">#{{ r.rider.race_number }}</span>
            <span class="ml-2 font-semibold">{{ r.rider.first_name }} {{ r.rider.last_name }}</span>
          </span>
          <span class="text-[11px] uppercase tracking-[0.06em] text-fg-faint">
            {{ r.category.code }} · {{ r.season_year }}
          </span>
        </li>
      </ul>
      <p v-else class="px-3 py-2 text-[13px] text-fg-muted">{{ copy.search.empty }}</p>
    </div>
  </div>
</template>
