// Ergonomic type aliases over the openapi-typescript generated schema.
//
// Regenerate the raw schema file with:  `npm run generate:api-types`
// This file (api.types.ts) stays hand-curated — shorter names, easier imports.

import type { components } from './api.openapi';

type S = components['schemas'];

export type RiderRef = S['RiderRef'];
export type CategoryRef = S['CategoryRef'];
export type EventRef = S['EventRef'];
export type SeasonRef = S['SeasonRef'];

export type SeasonListOut = S['SeasonListOut'];
export type SeasonDetailOut = S['SeasonDetailOut'];

export type RiderEventEntryOut = S['RiderEventEntryOut'];
export type StandingsRowOut = S['StandingsRowOut'];
export type StandingsOut = S['StandingsOut'];

export type EventListOut = S['EventListOut'];
export type EventDetailOut = S['EventDetailOut'];

export type EventResultRowOut = S['EventResultRowOut'];
export type EventResultsOut = S['EventResultsOut'];

export type RiderDisambigEntryOut = S['RiderDisambigEntryOut'];
export type RiderDisambigOut = S['RiderDisambigOut'];

export type RiderResultOut = S['RiderResultOut'];
export type RiderProfileOut = S['RiderProfileOut'];

export type RiderSearchResultOut = S['RiderSearchResultOut'];
export type RiderSearchOut = S['RiderSearchOut'];

// Cross-season search response. Not in the generated openapi schema yet
// (regenerate via `npm run generate:api-types` after the next backend
// build). Shape mirrors backend GlobalRiderSearchOut.
export interface GlobalRiderSearchOut {
  query: string;
  results: RiderSearchResultOut[];
}

export type RiderCareerSeasonOut = S['RiderCareerSeasonOut'];
export type RiderCareerOut = S['RiderCareerOut'];

export type DeviceCount = S['DeviceCount'];
export type CategoryVisitCount = S['CategoryVisitCount'];
export type RecentVisit = S['RecentVisit'];
export type StatsOut = S['StatsOut'];

export type TrackIn = S['TrackIn'];
export type TrackOut = S['TrackOut'];
