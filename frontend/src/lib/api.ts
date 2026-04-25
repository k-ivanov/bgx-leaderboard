// Typed fetch helpers against the BGX FastAPI backend.
//
// Used from Astro page frontmatter + `getStaticPaths` during the build, and
// from Vue islands at runtime. In dev, Astro's Vite server proxies `/api/*`
// to `http://localhost:5001` (see astro.config.mjs).
//
// Build-time URL resolution: when Astro runs `astro build`, it executes page
// frontmatter in Node — which has no notion of "current origin." Set
// `API_URL` in the build environment to point at a reachable FastAPI.

import type {
  EventDetailOut,
  EventListOut,
  EventResultsOut,
  RiderDisambigOut,
  RiderProfileOut,
  SeasonDetailOut,
  SeasonListOut,
  StandingsOut,
  StatsOut,
} from './api.types';

function apiBase(): string {
  // Browser runtime — use same-origin relative URLs. In dev, Astro's Vite
  // dev server proxies /api/* to the backend on :5001 (astro.config.mjs).
  // In production the backend serves the frontend, so /api/* is same-origin.
  if (typeof window !== 'undefined') {
    return '';
  }
  // Node / SSR / build: fetch() requires an absolute URL. Prefer API_URL,
  // fall back to 127.0.0.1 (IPv4) explicitly — "localhost" resolves to
  // IPv6 (::1) first in Node 18+ and uvicorn binds IPv4 by default,
  // which causes ECONNREFUSED on an otherwise reachable backend.
  const override = (globalThis as any).process?.env?.API_URL;
  return (override ?? 'http://127.0.0.1:5001').replace(/\/+$/, '');
}

async function getJson<T>(path: string): Promise<T> {
  const url = `${apiBase()}${path}`;
  const res = await fetch(url, { headers: { accept: 'application/json' } });
  if (!res.ok) {
    throw new Error(
      `API ${res.status} ${res.statusText} on ${path}: ${await res.text().catch(() => '')}`,
    );
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSeasons: (): Promise<SeasonListOut> => getJson('/api/seasons'),

  getSeason: (year: number): Promise<SeasonDetailOut> =>
    getJson(`/api/seasons/${year}`),

  getLeaderboard: (year: number, categoryCode: string): Promise<StandingsOut> =>
    getJson(`/api/seasons/${year}/standings/${categoryCode}`),

  listRaces: (year: number): Promise<EventListOut> =>
    getJson(`/api/seasons/${year}/events`),

  getRace: (year: number, slug: string): Promise<EventDetailOut> =>
    getJson(`/api/seasons/${year}/events/${slug}`),

  getRaceResults: (
    year: number,
    categoryCode: string,
    slug: string,
  ): Promise<EventResultsOut> =>
    getJson(
      `/api/seasons/${year}/categories/${categoryCode}/events/${slug}`,
    ),

  getRiderDisambiguation: (
    year: number,
    raceNumber: number,
  ): Promise<RiderDisambigOut> =>
    getJson(`/api/seasons/${year}/riders/${raceNumber}`),

  getRiderProfile: (
    year: number,
    raceNumber: number,
    slug: string,
  ): Promise<RiderProfileOut> =>
    getJson(`/api/seasons/${year}/riders/${raceNumber}/${slug}`),

  getStats: (): Promise<StatsOut> => getJson('/api/stats'),

  /** POST hook invoked from the client-side router (or a small inline script)
   * to record a visit. Fire-and-forget. */
  track: (input: {
    page: string;
    category?: string | null;
    season_year?: number | null;
    event_slug?: string | null;
    rider_slug?: string | null;
  }): Promise<{ ok: boolean }> =>
    fetch(`${apiBase()}/api/track`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
      keepalive: true,
    }).then(r => r.json()),
};
