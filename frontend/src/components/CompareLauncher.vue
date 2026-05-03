<script setup lang="ts">
// Tiny island for the "Сравни с…" button on the rider profile.
// Click toggles a dropdown rooted at CompareSearch; picking a rider
// navigates to /compare?a={current}&b={picked}. Self-contained so the
// rider-profile Astro page doesn't have to wire any events.
import { ref } from 'vue';
import CompareSearch from './CompareSearch.vue';
import type { RiderSearchResultOut } from '~/lib/api.types';
import { copy } from '~/lib/copy';

const props = defineProps<{
  currentSlug: string;
}>();

const open = ref(false);

function onSelect(r: RiderSearchResultOut) {
  const a = encodeURIComponent(props.currentSlug);
  const b = encodeURIComponent(r.rider.slug);
  window.location.href = `/compare?a=${a}&b=${b}`;
}
</script>

<template>
  <div class="relative inline-block">
    <button
      type="button"
      class="rounded-md border border-border bg-bg-base px-3 py-1.5 text-sm font-semibold text-fg-muted transition-colors hover:border-accent hover:text-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      :aria-label="copy.compare.fromRiderProfileAria"
      :aria-expanded="open"
      @click="open = !open"
    >
      {{ copy.compare.fromRiderProfile }}
    </button>
    <div v-if="open" class="absolute left-0 mt-2 w-72 z-30">
      <CompareSearch
        :exclude-slug="currentSlug"
        :placeholder="copy.compare.pickSecondPlaceholder"
        @select="onSelect"
      />
    </div>
  </div>
</template>
