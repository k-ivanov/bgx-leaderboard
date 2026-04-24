// Microcopy library — single source of truth for every user-facing string.
// Design rule: no inline strings in `.astro` or `.vue` components.
// See design-review.md §14 (vocabulary) + §16 (microcopy).
//
// Language: Bulgarian. Rider names and team names in the DB are already in
// Cyrillic. Page titles, meta descriptions, JSON-LD structured-data terms
// that follow schema.org conventions ("Hard Enduro", "Enduro rider") stay
// in English — see app/main.py and the page frontmatter.

export const copy = {
  app: {
    brand: 'BGX.',                   // kept as brand mark
    brandSubtitle: 'Хард Ендуро',
    footer: (version: string) =>
      `Шампионат БГХ Хард Ендуро · Неофициален · v${version}`,
  },
  nav: {
    leaderboard: 'Класиране',
    races: 'Състезания',
    stats: 'Статистика',
    home: 'Начало',
  },
  home: {
    h1: 'Добре дошли в BGX Хард Ендуро',
    lead:
      'Това са неофициални резултати от Българския Екстремен Ендуро Шампионат, ' +
      'събрани от навигационните дни на всяко състезание. Сайтът не е обвързан ' +
      'с Българската Федерация по Мотоциклетизъм или с организаторите — той е ' +
      'фен-проект, който прави резултатите по-лесни за проследяване.',
    whatYoullFindHeading: 'Какво ще намерите тук:',
    bullets: [
      'Класирания по категории за всеки сезон от 2024 г. насам',
      'Резултати от всяко състезание, включително ден 1 и ден 2 за двудневните кръгове',
      'Профили на състезателите — екип, мотоциклет и цялата серия резултати през сезона',
    ],
    closing: 'Изберете сезон по-долу или използвайте менюто горе.',
    seasonsHeading: 'Сезони',
    seasonCurrentBadge: 'Текущ',
    seasonRidersFmt: (n: number) => `${n} състезатели`,
    seasonRacesFmt: (n: number) => `${n} състезания`,
    seasonCtaFmt: (category: string) => `Виж класиране ${category} →`,
  },
  leaderboard: {
    h1: (year: number, category: string) =>
      `Класиране ${category} · ${year}`,
    subtitle: 'Български шампионат по Хард Ендуро',
    empty: (category: string) =>
      `Все още няма състезатели в категория ${category}.`,
    statLeader: 'Лидер',
    statRaces: 'Състезания',
    statGap: 'Преднина 1→2',
    statActive: 'Активни състезатели',
    colHash: '#',
    colNumber: '№',
    colRider: 'Състезател',
    colTotal: 'Общо',
    colRaced: 'Участия',
    colBest: 'Най-добро',
    colDropped: 'Отпаднал',
  },
  races: {
    h1: (year: number) => `Състезания ${year}`,
    subtitleFmt: (total: number, upcoming: number, completed: number) =>
      `${total} състезания · ${upcoming} предстоящи · ${completed} завършени`,
    empty: (year: number) =>
      `Все още няма насрочени състезания за ${year} г.`,
    statusCompleted: '✓ Завършено',
    statusUpcoming: 'Предстоящо',
    colHash: '#',
    colRace: 'Състезание',
    colLocation: 'Място',
    colDate: 'Дата',
    colStatus: 'Статус',
  },
  raceResults: {
    h1: (round: number, raceName: string, categoryName: string) =>
      `R${round} · ${raceName} — ${categoryName}`,
    subtitleFmt: (dateLong: string, locationFull: string) =>
      `${dateLong} · ${locationFull}`,
    empty: 'Резултатите за тази категория и състезание все още не са налични.',
    backToLeaderboard: (category: string) =>
      `← Назад към класиране ${category}`,
    prevNextFmt: (prev: string | null, next: string | null) => {
      if (prev && next) return `← ${prev} · ${next} →`;
      if (prev) return `← ${prev}`;
      if (next) return `${next} →`;
      return '';
    },
    colHash: '#',
    colNumber: '№',
    colRider: 'Състезател',
    colTime: 'Време',
    colPoints: 'Т.',                 // Bulgarian abbreviation for Points (Точки)
    colLaps: 'Обиколки',
    colGps: 'GPS',                   // kept — widely understood motorsport abbrev
    dnf: 'DNF',                      // kept — international motorsport convention
    dns: 'DNS',
  },
  raceOverview: {
    h1: (raceName: string) => raceName,
    subtitleFmt: (round: number, dateLong: string, locationFull: string) =>
      `Кръг ${round} · ${dateLong} · ${locationFull}`,
    sectionResults: 'Резултати по категория',
    categoryPendingLabel: '(предстои)',
    empty: 'Подробности за състезанието скоро.',
    viewResults: 'Виж резултати →',
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
      `Най-добро: ${bestFinish} · Участия: ${racesEntered} · Общо точки: ${totalPoints}`,
    sectionSeasonResults: (category: string) =>
      `Резултати за сезона · ${category}`,
    empty: (year: number) =>
      `Няма резултати за този състезател за сезон ${year}.`,
    entriesFmt: (entered: number, total: number) =>
      `Участия в ${entered} от ${total} състезания този сезон.`,
    backToCategory: (category: string) =>
      `← Назад към класиране ${category}`,
    disambigH1: (raceNumber: number, year: number) =>
      `Състезател №${raceNumber} · Сезон ${year}`,
    disambigHelp: (count: number, raceNumber: number) =>
      count === 2
        ? `Двама състезатели се състезават с номер ${raceNumber} този сезон:`
        : `${count} състезатели се състезават с номер ${raceNumber} този сезон:`,
    colRound: 'Кръг',
    colRace: 'Състезание',
    colDate: 'Дата',
    colPosition: 'Позиция',
    colPoints: 'Точки',
    colTime: 'Време',
  },
  stats: {
    h1: 'Вътрешна статистика',
    subtitleLast30: 'Последните 30 дни',
    statVisits: 'Посещения',
    statDesktop: 'Десктоп',
    statMobile: 'Мобилни',
    statUnknown: 'Неизвестно',
    sectionByCategory: 'Посещения по категория',
    sectionRecent: 'Последни посещения (25)',
    empty: 'Все още няма регистрирани посещения.',
    colTime: 'Време',
    colPage: 'Страница',
    colCategory: 'Категория',
    colSeason: 'Сезон',
    colVisits: 'Посещения',
    colDevice: 'Устройство',
    unavailable: 'Статистиката не е налична в момента — проверете отново след следващия билд.',
  },
  notFound: {
    h1: '404',
    subtitle: 'Не можем да намерим тази страница.',
    helpBody: 'Линкът може да е стар или страницата да е премахната.',
    ctaCurrentLeaderboard: (year: number) =>
      `→ Към класирането за ${year}`,
    pageTitle: 'Страницата не е намерена · BGX Хард Ендуро',
    metaDescription: 'Страницата, която търсите, не съществува на bgx.',
  },
  error500: {
    h1: 'Нещо се обърка',
    subtitle: 'Възникна неочаквана грешка. Моля опитайте отново след малко.',
    cta: 'Към началната страница',
  },
  common: {
    backToTop: '↑ Нагоре',
    loading: 'Зареждане…',
    noTime: '—',
    rider: 'състезател',
    themeToggleToLight: 'Превключи към светла тема',
    themeToggleToDark: 'Превключи към тъмна тема',
  },

  // SEO title + meta-description templates. English brand "BGX Хард Ендуро"
  // in Bulgarian Cyrillic transliteration (Хард Ендуро is the standard spelling).
  seo: {
    brand: 'BGX Хард Ендуро',
    leaderboardTitle: (year: number, category: string) =>
      `Класиране ${category} · ${year} · BGX Хард Ендуро`,
    leaderboardDescription: (
      year: number,
      category: string,
      riderCount: number,
      racesCompleted: number,
      totalRaces: number,
    ) =>
      `Класиране за категория ${category} от сезон ${year} на шампионата БГХ Хард Ендуро. ` +
      `${riderCount} състезатели, ${racesCompleted} от ${totalRaces} завършени състезания.`,
    racesTitle: (year: number) =>
      `Състезания ${year} · Шампионат БГХ Хард Ендуро`,
    racesDescription: (year: number, total: number, first: string | null, last: string | null) =>
      `Календар на състезанията за сезон ${year} от шампионата БГХ Хард Ендуро. ` +
      `${total} състезания${first && last ? ` от ${first} до ${last}` : ''}.`,
    raceOverviewTitle: (raceName: string, round: number, year: number) =>
      `${raceName} · Кръг ${round} · ${year} · BGX Хард Ендуро`,
    raceOverviewDescription: (
      round: number,
      year: number,
      raceName: string,
      location: string | null | undefined,
      dateLong: string | null | undefined,
    ) =>
      `Кръг ${round} от шампионата БГХ Хард Ендуро ${year}. ${raceName}` +
      (location ? `, ${location}` : '') +
      (dateLong ? `, ${dateLong}` : '') + '.',
    raceResultsTitle: (raceName: string, category: string, year: number) =>
      `${raceName} резултати · ${category} · ${year} · BGX Хард Ендуро`,
    raceResultsDescription: (
      category: string,
      round: number,
      raceName: string,
      year: number,
      winnerName: string | null,
    ) =>
      winnerName
        ? `Резултати за категория ${category} от кръг ${round} ${raceName}, ` +
          `BGX Хард Ендуро ${year}. Победител: ${winnerName}.`
        : `Резултати за категория ${category} от кръг ${round} ${raceName}, ` +
          `BGX Хард Ендуро ${year}.`,
    riderTitle: (first: string, last: string, category: string, year: number) =>
      `${first} ${last} · ${category} · ${year} · BGX Хард Ендуро`,
    riderDescription: (
      first: string,
      last: string,
      raceNumber: number,
      category: string,
      bestFinish: string,
      racesEntered: number,
      year: number,
    ) =>
      `${first} ${last}, №${raceNumber}, категория ${category}. ` +
      `Най-добро класиране: ${bestFinish}. Участия в ${racesEntered} състезания от сезон ${year} на шампионата БГХ Хард Ендуро.`,
    riderDisambigTitle: (raceNumber: number, year: number) =>
      `Състезател №${raceNumber} · ${year} · BGX Хард Ендуро`,
    riderDisambigDescription: (count: number, raceNumber: number, year: number) =>
      `${count} състезатели се състезават с номер ${raceNumber} в шампионата БГХ Хард Ендуро ${year}.`,
    statsTitle: 'Вътрешна статистика · BGX',
    statsDescription: 'Вътрешна статистика за посещенията на сайта БГХ Хард Ендуро.',
    siteName: 'Шампионат БГХ Хард Ендуро',
  },
} as const;
