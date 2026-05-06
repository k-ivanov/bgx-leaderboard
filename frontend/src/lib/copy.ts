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
    brand: 'BGX Hard Enduro Championship',                   // kept as brand mark
    // brandSubtitle: 'Хард Ендуро',
    footer: (version: string) =>
      `Шампионат БГХ Хард Ендуро · Неофициален · ${version}`,
  },
  nav: {
    leaderboard: 'Класиране',
    races: 'Състезания',
    stats: 'Статистика',
    home: 'Начало',
  },
  search: {
    placeholder: 'Търсене на състезател…',
    aria: 'Търсене на състезател',
    empty: 'Няма резултати.',
  },
  home: {
    h1: 'BGX Хард Ендуро Шампионат',
    h1Sub: 'Неофициални Резултати',
    lead:
      'Това са неофициални резултати от Българския Екстремен Ендуро Шампионат, ' +
      'събрани от навигационните дни на всяко състезание тип Хард Ендуро.',
    cta: 'Резултати',
  },
  results: {
    titleStem: 'Резултати',
    metaDescription:
      'Класирания и резултати от шампионата БГХ Хард Ендуро — избери сезон, категория и състезание.',
    seasonLabel: 'Сезон',
    seasonAria: 'Избор на сезон',
    generalTab: 'Генерално класиране',
    loading: 'Зареждане…',
    errorTitle: 'Грешка при зареждане',
    errorBody: 'Моля опитайте отново.',
    errorRetry: 'Опитай пак',
    emptyStandings: (category: string) => `Все още няма състезатели в категория ${category}.`,
    emptyRace: 'Резултатите за тази категория и състезание все още не са налични.',
    leaderboardH1: (year: number, category: string) => `Класиране ${category} · Сезон ${year}`,
    raceH1: (round: number, raceName: string, category: string) =>
      `R${round} · ${raceName} — ${category}`,
    raceSubtitle: (round: number) => `Кръг ${round}`,
    colHash: '#',
    colNumber: '№',
    colRider: 'Състезател',
    colTotal: 'Точки',
    colRaced: 'Участия',
    colBest: 'Най-добро',
    colTime: 'Време',
    colPoints: 'Т.',
    colLaps: 'Обиколки',
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
    generalTab: 'ГЕНЕРАЛНО КЛАСИРАНЕ',
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
  riderProfile: {
    titleFmt: (first: string, last: string) => `${first} ${last} · BGX Хард Ендуро`,
    descriptionFmt: (
      first: string,
      last: string,
      latestCategory: string,
      latestSeason: number,
    ) =>
      `Кариерен профил на ${first} ${last} в шампионата БГХ Хард Ендуро. ` +
      `Последен сезон: ${latestSeason} · ${latestCategory}.`,
    careerHeading: 'Кариера',
    seasonHeading: (year: number, category: string, raceNumber: number) =>
      `Сезон ${year} · ${category} · #${raceNumber}`,
    colSeason: 'Сезон',
    colCategory: 'Категория',
    colNumber: '№',
    colRanking: 'Класиране',
    colRaces: 'Участия',
    colBest: 'Най-добро',
    colPoints: 'Точки',
    colRound: 'Кръг',
    colRace: 'Състезание',
    colPosition: 'Позиция',
    colTime: 'Време',
    metaFmt: (team: string | null | undefined, bike: string | null | undefined, category: string) =>
      [team, bike, category].filter(Boolean).join(' · '),
    statsFmt: (bestFinish: string, racesEntered: number, totalPoints: number) =>
      `Най-добро: ${bestFinish} · Участия: ${racesEntered} · Общо точки през кариерата: ${totalPoints}`,
    notFound: 'Не намерихме състезател с този идентификатор.',
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
    careerHeading: 'Кариера',
    colSeason: 'Сезон',
    colCategory: 'Категория',
    colNumber: '№',
    colRaces: 'Участия',
    colBest: 'Най-добро',
    colPoints: 'Точки',
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
    colTime: 'Време',
  },
  racesPage: {
    titleStem: 'Състезания',
    metaDescription: 'Календар на състезанията от шампионата БГХ Хард Ендуро — минали и предстоящи.',
    h1: (year: number) => `Състезания ${year}`,
    subtitleFmt: (total: number, completed: number, upcoming: number) =>
      `${total} кръга · ${completed} завършени · ${upcoming} предстоящи`,
    empty: (year: number) => `Все още няма насрочени състезания за ${year}.`,
    statusCompleted: '✓ Завършено',
    statusNext: 'Следващо',
    statusUpcoming: 'Предстоящо',
    statusTbd: 'Дата TBD',
    daysUntilFmt: (n: number) =>
      n === 0 ? 'днес' : n === 1 ? 'утре' : n < 0 ? `преди ${-n} дни` : `след ${n} дни`,
    legendCompleted: 'Завършено',
    legendNext: 'Следващо',
    legendUpcoming: 'Предстоящо',
    fbEventCta: 'Facebook събитие',
    leaderboardCta: 'Виж класирането',
    fullPageCta: 'Към страницата на състезанието →',
    descriptionFallback: 'Подробности за състезанието скоро.',
    detailHeading: 'Подробности',
    seasonLabel: 'Сезон',
    locationLabel: 'Локация',
    dateLabel: 'Дата',
    roundLabel: 'Кръг',
    notFound: 'Не намерихме това състезание.',
    raceNotFoundTitle: 'Състезание не е намерено',
    backToCalendar: '← Към календара',
  },
  compare: {
    titleStem: 'Сравнение',
    metaDescription:
      'Сравни двама състезатели от шампионата БГХ Хард Ендуро — кариерни статистики и лице в лице резултати.',
    h1: 'Сравнение на състезатели',
    pickBoth: 'Изберете два състезателя за съпоставка.',
    versus: 'срещу',
    pickFirstPlaceholder: 'Първи състезател…',
    pickSecondPlaceholder: 'Втори състезател…',
    fromRiderProfile: 'Сравни с…',
    fromRiderProfileAria: 'Сравни този състезател с друг',
    statsHeading: 'Кариерни статистики',
    statSeasons: 'Сезони',
    statStarts: 'Стартове',
    statFinishes: 'Финиша',
    statBestOverall: 'Най-добро',
    statTotalPoints: 'Точки общо',
    statCategories: 'Категории',
    headToHeadHeading: 'Лице в лице',
    headToHeadCount: (n: number) => `${n} общи състезания`,
    tieLabel: 'Равно',
    noShared: 'Тези двама състезатели не са се срещали в едно състезание.',
    colRace: 'Състезание',
    colWinner: 'Победител',
    winnerTie: '—',
    summaryFmt: (a: string, aWins: number, b: string, bWins: number, ties: number) =>
      `Резултати: ${a} ${aWins} · ${b} ${bWins} · Равно ${ties}`,
    sameRiderError: 'Не може да сравните състезател със самия себе си.',
    riderNotFound: 'Не намерихме един от състезателите.',
    loading: 'Зареждане…',
  },
  stats: {
    h1: 'Вътрешна статистика',
    subtitleLast30: 'Последните 30 дни',
    statVisits: 'Посещения',
    statDesktop: 'Десктоп',
    statMobile: 'Мобилни',
    statUnknown: 'Неизвестно',
    statUniqueToday: 'Уникални днес',
    statUnique7d: 'Уникални за 7 дни',
    statUnique30d: 'Уникални за 30 дни',
    statSessionsToday: 'Сесии днес',
    statAvgSession: 'Средна сесия',
    sectionByCategory: 'Посещения по категория',
    sectionByRace: 'Най-гледани състезания',
    sectionByRider: 'Най-гледани състезатели',
    sectionComparisons: 'Най-сравнявани двойки',
    sectionRecent: 'Последни посещения (25)',
    empty: 'Все още няма регистрирани посещения.',
    emptyComparisons: 'Все още няма направени сравнения.',
    colTime: 'Време',
    colPage: 'Страница',
    colCategory: 'Категория',
    colSeason: 'Сезон',
    colVisits: 'Посещения',
    colDevice: 'Устройство',
    colRace: 'Състезание',
    colRider: 'Състезател',
    colRiderA: 'Състезател А',
    colRiderB: 'Състезател Б',
    unavailable: 'Статистиката не е налична в момента — проверете отново след следващия билд.',
    authTitle: 'Достъп само за администратори',
    authIntro: 'Въведете паролата, за да видите статистиката.',
    authUsername: 'Потребител',
    authPassword: 'Парола',
    authSubmit: 'Вход',
    authError: 'Грешна парола.',
    authLogout: 'Изход',
    loading: 'Зареждане…',
    lastUpdated: 'Обновено',
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
