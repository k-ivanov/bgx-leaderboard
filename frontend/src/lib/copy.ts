// Microcopy library — single source of truth for every user-facing string.
// Design rule: no inline strings in `.astro` or `.vue` components.
// See design-review.md §14 (vocabulary) + §16 (microcopy).

export const copy = {
  app: {
    brand: 'BGX.',
    brandSubtitle: 'Hard Enduro',
    footer: (version: string) =>
      `BGX Hard Enduro Championship · Unofficial · v${version}`,
  },
  nav: {
    leaderboard: 'Leaderboard',
    races: 'Races',
    stats: 'Stats',
  },
  leaderboard: {
    h1: (year: number, category: string) => `${year} ${category} Leaderboard`,
    subtitle: 'Bulgarian Hard Enduro Championship',
    empty: (category: string) => `No riders in ${category} yet.`,
    statLeader: 'Leader',
    statRaces: 'Races',
    statGap: 'Gap 1→2',
    statActive: 'Active riders',
    colHash: '#',
    colNumber: 'No.',
    colRider: 'Rider',
    colTotal: 'Total',
    colRaced: 'Raced',
    colBest: 'Best',
    colDropped: 'Dropped',
  },
  races: {
    h1: (year: number) => `${year} Races`,
    subtitleFmt: (total: number, upcoming: number, completed: number) =>
      `${total} races · ${upcoming} upcoming · ${completed} completed`,
    empty: (year: number) => `No races scheduled for ${year} yet.`,
    statusCompleted: '✓ Completed',
    statusUpcoming: 'Upcoming',
    colHash: '#',
    colRace: 'Race',
    colLocation: 'Location',
    colDate: 'Date',
    colStatus: 'Status',
  },
  raceResults: {
    h1: (round: number, raceName: string, categoryName: string) =>
      `R${round} · ${raceName} — ${categoryName}`,
    subtitleFmt: (dateLong: string, locationFull: string) =>
      `${dateLong} · ${locationFull}`,
    empty: "Results for this category and race aren't in yet.",
    backToLeaderboard: (category: string) =>
      `← Back to ${category} Leaderboard`,
    prevNextFmt: (prev: string | null, next: string | null) => {
      if (prev && next) return `← ${prev} · ${next} →`;
      if (prev) return `← ${prev}`;
      if (next) return `${next} →`;
      return '';
    },
    colHash: '#',
    colNumber: 'No.',
    colRider: 'Rider',
    colTime: 'Time',
    colPoints: 'Pts',
    colLaps: 'Laps',
    colGps: 'GPS',
    dnf: 'DNF',
    dns: 'DNS',
  },
  raceOverview: {
    h1: (raceName: string) => raceName,
    subtitleFmt: (round: number, dateLong: string, locationFull: string) =>
      `Round ${round} · ${dateLong} · ${locationFull}`,
    sectionResults: 'Results by category',
    categoryPendingLabel: '(pending)',
    empty: 'Race details coming soon.',
  },
  rider: {
    metaFmt: (
      team: string | null | undefined,
      bike: string | null | undefined,
      category: string,
    ) => [team, bike, category].filter(Boolean).join(' · '),
    statsFmt: (
      bestFinish: string,
      racesEntered: number,
      totalPoints: number,
    ) =>
      `Best: ${bestFinish} · Races entered: ${racesEntered} · Total points: ${totalPoints}`,
    sectionSeasonResults: (category: string) => `Season results · ${category}`,
    empty: (year: number) => `This rider has no results yet for ${year}.`,
    entriesFmt: (entered: number, total: number) =>
      `Entered ${entered} of ${total} races this season.`,
    backToCategory: (category: string) =>
      `← Back to ${category} Leaderboard`,
    disambigH1: (raceNumber: number, year: number) =>
      `Rider #${raceNumber} · ${year} Season`,
    disambigHelp: (count: number, raceNumber: number) =>
      count === 2
        ? `Two riders compete with number ${raceNumber} this season:`
        : `${count} riders compete with number ${raceNumber} this season:`,
  },
  stats: {
    h1: 'Private analytics',
    subtitleLast30: 'Last 30 days',
    statVisits: 'Visits',
    statDesktop: 'Desktop',
    statMobile: 'Mobile',
    statUnknown: 'Unknown',
    sectionByCategory: 'Visits by category',
    sectionRecent: 'Recent visits (last 25)',
    empty: 'No visits recorded yet.',
  },
  notFound: {
    h1: '404',
    subtitle: "We can't find that page.",
    helpBody: 'The link may be old or the page may have been removed.',
    ctaCurrentLeaderboard: (year: number) =>
      `Go to the ${year} Leaderboard`,
  },
  error500: {
    h1: 'Something went wrong',
    subtitle:
      'An unexpected error occurred. Please try again in a moment.',
    cta: 'Go to the home page',
  },
  common: {
    backToTop: '↑ Top',
    loading: 'Loading…',
    noTime: '—',
  },
} as const;
