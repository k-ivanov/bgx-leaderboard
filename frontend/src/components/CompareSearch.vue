<script setup lang="ts">
// Search dropdown for the compare flow. Same UX as RiderSearch in the nav
// (debounced /api/riders/search, arrow-key nav, Enter to select, Esc to
// close), but it emits a `select` event instead of navigating — callers
// decide what to do with the picked rider. Used three times: rider
// profile "Сравни с…" button + the two slots on /compare's empty state.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { GlobalRiderSearchOut, RiderSearchResultOut } from '~/lib/api.types';
import { copy } from '~/lib/copy';

const props = defineProps<{
  // When set, this slug is filtered out of the dropdown so a rider can't
  // be picked twice (e.g. the current rider on their own profile).
  excludeSlug?: string;
  // Override placeholder copy when used outside the nav.
  placeholder?: string;
  // ARIA label override for screen readers.
  ariaLabel?: string;
  // Width preset; nav uses the default narrow form, /compare wants wider.
  variant?: 'nav' | 'wide';
}>();

const emit = defineEmits<{
  (e: 'select', result: RiderSearchResultOut): void;
}>();

const query = ref('');
const results = ref<RiderSearchResultOut[]>([]);
const open = ref(false);
const loading = ref(false);
const cursor = ref(-1);

let debounceHandle: ReturnType<typeof setTimeout> | null = null;
let abortController: AbortController | null = null;

const inputClasses = computed(() =>
  props.variant === 'wide'
    ? 'w-full rounded-md border border-border bg-bg-elevated px-4 py-2.5 text-[15px] focus:border-accent focus:outline-none'
    : 'w-44 sm:w-56 rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-[13px] focus:border-accent focus:outline-none',
);

const dropdownClasses = computed(() =>
  props.variant === 'wide'
    ? 'absolute left-0 right-0 mt-1 rounded-md border border-border bg-bg-elevated shadow-lg z-30'
    : 'absolute right-0 mt-1 w-72 rounded-md border border-border bg-bg-elevated shadow-lg z-30',
);

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
    // Filter out the excluded slug client-side; the API doesn't take an
    // exclusion param and we don't want to duplicate the search logic.
    results.value = props.excludeSlug
      ? data.results.filter(r => r.rider.slug !== props.excludeSlug)
      : data.results;
    open.value = true;
    cursor.value = results.value.length > 0 ? 0 : -1;
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

function pick(r: RiderSearchResultOut) {
  emit('select', r);
  clear();
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
      pick(results.value[cursor.value]);
    }
  } else if (e.key === 'Escape') {
    clear();
  }
}

function onBlur() {
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
      :placeholder="placeholder ?? copy.search.placeholder"
      :value="query"
      @input="onInput"
      @focus="open = results.length > 0"
      @blur="onBlur"
      :class="inputClasses"
      autocomplete="off"
      :aria-label="ariaLabel ?? copy.search.aria"
    />

    <div
      v-if="open && (results.length > 0 || showEmpty)"
      :class="dropdownClasses"
    >
      <ul v-if="results.length > 0" class="max-h-80 overflow-y-auto">
        <li
          v-for="(r, i) in results"
          :key="`${r.season_year}-${r.rider.race_number}-${r.rider.slug}`"
          @mousedown="pick(r)"
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
