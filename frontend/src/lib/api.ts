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
  // In SSR/build contexts, prefer API_URL; fall back to localhost.
  if (typeof process !== 'undefined' && process.env?.API_URL) {
    return process.env.API_URL.replace(/\/+$/, '');
  }
  // In the browser, use same-origin (empty = relative).
  return '';
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
  }): Promise<{ ok: boolean }> => {
    const base = typeof window === 'undefined' ? apiBase() : '';
    return fetch(`${base}/api/track`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
    }).then(r => r.json());
  },
};
