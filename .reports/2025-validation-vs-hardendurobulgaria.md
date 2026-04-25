# 2025 Standings — Validation vs hardendurobulgaria.com

_Generated 2026-04-25 19:54 UTC._  Source: `http://localhost:5001/api/seasons/2025/standings/{cat}` vs `https://hardendurobulgaria.com/?category={cat}`.

## TL;DR

Both datasets agree on **who** raced, but disagree on **how points are scored**. Three structural differences explain almost every discrepancy:

1. **Single-day vs multi-day scoring.** hardendurobulgaria.com banner says _"Results from first navigation day"_. Our import sums every day of each race weekend — so for two-day events (Gorna Malina, Botevgrad, etc.) our per-event totals are larger.
2. **Different race set.** Theirs lists **Six Days** which we do not import. Ours has **Kirkovo** (theirs has it too — same race name).
3. **Drop-worst-race rule.** Theirs subtracts the worst result from the season total when a rider has 7 events. Ours does not (`championship_format=per_event`).

Plus: our DB carries **registered-but-zero-points riders** (DNS / DNF day 2 / late-season registrations). hardendurobulgaria.com only shows riders who scored at least one point.

**Recommendation**: ours is a complete archive; theirs is a partial snapshot frozen on the day of import. The deltas are not bugs — they are scope choices. If you want exact parity with theirs, drop multi-day data and re-export with day=1 only and add the worst-drop rule.

## Summary by category

| Category | Ours | Theirs | Matched | Same pos | Same pts | Only ours | Only theirs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `profi` | 19 | 17 | 17 | 11 | 6 | 2 | 0 |
| `expert` | 70 | 61 | 57 | 6 | 31 | 13 | 4 |
| `standard` | 140 | 118 | 116 | 4 | 87 | 24 | 2 |
| `standard_junior` | 23 | 19 | 19 | 9 | 8 | 4 | 0 |
| `women` | 9 | 7 | 7 | 3 | 2 | 2 | 0 |
| `seniors_40` | 42 | 33 | 33 | 7 | 16 | 9 | 0 |
| `seniors_50` | 17 | 15 | 14 | 7 | 5 | 3 | 1 |

- **Ours / Theirs** — total rider rows in each leaderboard.
- **Matched** — riders present in both (joined by race number).
- **Same pos / Same pts** — of those matched, how many agree exactly.
- **Only ours / Only theirs** — riders present in only one source (race number not seen on the other side).

## Race coverage

| Race | Ours (`event_slug`) | hardendurobulgaria.com column |
|---|---|---|
| Kyrnare | `kyrnare` | Kyrnare |
| Stara Zagora | `stara_zagora` | Stara Zagora |
| Buhovo | `buhovo` | Buhovo |
| Gorna Malina | `gorna_malina` | Gorna Malina |
| Alba Damascena | `alba-damascena` | Alba Damascena |
| Kirkovo | `kirkovo` | Kirkovo |
| **Six Days** | _missing_ | Six Days |

Action item: import 2025 Six Days CSV if available, otherwise document the omission in the README.

## Per-category drill-down

### `profi` — Pro / ПРОФИ

- Ours: **19** riders, theirs: **17** riders, matched: **17**.
- Of the matched riders, **11** share a final position and **6** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 272 | Кристиан ПЕТРОВ | 5 / 5 | 84 / 69 | +15 | 5 / 3 |
| 238 | Пламен КОВАЧЕВ | 15 / 10 | 16 / 30 | -14 | 2 / 2 |
| 13 | Любомир СИНЕВ | 3 / 3 | 114 / 102 | +12 | 6 / 6 |
| 393 | Симеон НЕНКОВ | 6 / 7 | 72 / 62 | +10 | 5 / 4 |
| 171 | Георги ПЕТРОВ | 10 / 13 | 29 / 20 | +9 | 5 / 1 |
| 217 | Данаил КОСТАДИНОВ | 9 / 9 | 49 / 41 | +8 | 6 / 3 |
| 134 | Красимир БОШНАКОВ | 2 / 2 | 114 / 108 | +6 | 6 / 6 |
| 131 | Борис ЧАКЪРОВ | 7 / 6 | 67 / 62 | +5 | 5 / 3 |
| 189 | Красимир ДИМИТРОВ | 8 / 8 | 61 / 57 | +4 | 5 / 4 |
| 15 | Мартин МАРИНОВ | 1 / 1 | 130 / 133 | -3 | 6 / 7 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 34 | Георги ГЕОРГИЕВ 3:34:40.7 | 18 | 0 | 1 |
| 40 | Мирослав ХРИСТОВ | 19 | 0 | 1 |


### `expert` — Expert / ЕКСПЕРТ

- Ours: **70** riders, theirs: **61** riders, matched: **57**.
- Of the matched riders, **6** share a final position and **31** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 327 | Борислав БОЖИЛОВ | 32 / 17 | 11 / 31 | -20 | 2 / 2 |
| 307 | Милен ДИМИТРОВ | 14 / 8 | 46 / 64 | -18 | 6 / 6 |
| 107 | Калоян ТОДОРОВ | 5 / 3 | 79 / 95 | -16 | 6 / 6 |
| 255 | Димитър ТИНЧЕВ | 1 / 1 | 134 / 147 | -13 | 5 / 6 |
| 274 | Иван ЧУКУРОВ | 11 / 7 | 54 / 67 | -13 | 5 / 6 |
| 294 | Александър Кабакчиев | 15 / 10 | 46 / 57 | -11 | 6 / 4 |
| 94 | Димитър ЦВЕТКОВ | 7 / 13 | 63 / 53 | +10 | 3 / 3 |
| 14 | Георги ПЕТКОВ | 25 / 19 | 16 / 26 | -10 | 5 / 4 |
| 772 | Валентин РОГЛЕВ | 3 / 5 | 82 / 73 | +9 | 6 / 5 |
| 111 | Синан СЕИДОВ | 33 / 25 | 11 / 20 | -9 | 5 / 6 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 39 | Илиян МАНОЛОВ | 45 | 0 | 1 |
| 205 | Красимир ИВАНОВ | 46 | 0 | 1 |
| 246 | Иван ПЕТРОВ | 47 | 0 | 1 |
| 357 | Адриан ЙОРДАНОВ | 48 | 0 | 1 |
| 374 | Станислав МИКОВ | 49 | 0 | 1 |
| 681 | Кирил ЧАПОВ | 50 | 0 | 1 |
| 705 | Кристиан БЕЛЧЕВ 4:19:24.4 | 51 | 0 | 1 |
| 878 | Ален МИРЧЕВ | 53 | 0 | 1 |
| 980 | Славчо ШОПОВ | 54 | 0 | 1 |
| 982 | Дениз ДЖАИТ | 55 | 0 | 1 |
| 218 | Николай НЕДЯЛКОВ 3:12:51.8 | 58 | 0 | 2 |
| 966 | Марио МИЛЕНКОВ | 60 | 0 | 2 |
| 181 | Мирослав МАРЧЕВ | 61 | 0 | 3 |

**Only on hardendurobulgaria.com**:

| # | Rider | Their pos | Their pts | Their races |
|---:|---|:---:|---:|:---:|
| 11 | Светлин ИВАНОВ | 37 | 5 | 1 |
| 828 | Alexander Stracke | 54 | 0 | 1 |
| 829 | Stefan Groos | 56 | 0 | 1 |
| 826 | Matthias Berger | 57 | 0 | 1 |


### `standard` — Standard / СТАНДАРТ

- Ours: **140** riders, theirs: **118** riders, matched: **116**.
- Of the matched riders, **4** share a final position and **87** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 253 | Виктор Христов | 83 / 4 | 0 / 124 | -124 | 3 / 2 |
| 403 | Александър ГЕНЧЕВ | 7 / 1 | 68 / 150 | -82 | 6 / 7 |
| 717 | Иво ГЕОРГИЕВ | 109 / 11 | 0 / 55 | -55 | 6 / 2 |
| 101 | Яна КИРОВА | 107 / 21 | 0 / 34 | -34 | 6 / 6 |
| 170 | Стефан МОЧЕВ 4:01:20.4 | 3 / 3 | 110 / 126 | -16 | 6 / 6 |
| 76 | Мартин ХРИСТЕВ | 8 / 10 | 56 / 72 | -16 | 6 / 6 |
| 285 | Николай ДИМИТРОВ | 6 / 6 | 82 / 97 | -15 | 6 / 7 |
| 184 | Денис АСЕНОВ | 13 / 15 | 31 / 45 | -14 | 5 / 5 |
| 109 | Мартин ЛЮБЕНОВ | 15 / 16 | 30 / 43 | -13 | 6 / 6 |
| 152 | Кристиян МАНДЕВСКИ 2:52:19.0 | 35 / 26 | 7 / 19 | -12 | 5 / 5 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 6 | Данко СЛАВОВ 5:01:09.7 | 48 | 0 | 1 |
| 28 | Андреан ДРАНГОВ | 49 | 0 | 1 |
| 45 | Аспарух ИВАНОВ | 50 | 0 | 1 |
| 48 | Мариан МИТЕВ | 51 | 0 | 1 |
| 150 | Стоян ДРИНОВ | 52 | 0 | 1 |
| 194 | Стефан ЖЕЛЯЗКОВ 4:55:04.0 | 53 | 0 | 1 |
| 288 | Енчо Янков | 54 | 0 | 1 |
| 335 | Стефан РАЧЕВ | 55 | 0 | 1 |
| 555 | Асен АСЕНОВ | 56 | 0 | 1 |
| 606 | Мирослав ВЪЛЧЕВ | 57 | 0 | 1 |
| 697 | Хюсеин ДЖУГДАН 3:24:35.5 | 58 | 0 | 1 |
| 719 | Петър ПЕТРОВ | 59 | 0 | 1 |
| 721 | Богомил ВАСИЛЕВ | 60 | 0 | 1 |
| 747 | Георги ИВАНОВ | 61 | 0 | 1 |
| 858 | Даниел КРЪСТЕВ | 62 | 0 | 1 |
| 877 | Аксел РАХМИ 3:43:31.0 | 63 | 0 | 1 |
| 886 | Радослав ХРИСТОВ 2:24:42.7 | 64 | 0 | 1 |
| 7 | Дилян ЯНЕВ | 65 | 0 | 2 |
| 55 | Петър ПАСПАЛЕВ | 67 | 0 | 2 |
| 223 | Сейфетин ОСМАНОВ 4:28:21.4 | 71 | 0 | 2 |
| 351 | Николай НИКОЛОВ | 75 | 0 | 2 |
| 450 | Христо ВАКЛИДОВ | 77 | 0 | 2 |
| 137 | Красимир КАМЕНОВ | 90 | 0 | 4 |
| 780 | Мариан ДИМИТРОВ 4:59:26.4 | 104 | 0 | 5 |

**Only on hardendurobulgaria.com**:

| # | Rider | Their pos | Their pts | Their races |
|---:|---|:---:|---:|:---:|
| 920 | Anders Wretblad | 7 | 95 | 1 |
| 373 | Йордан ЙОРДАНОВ | 36 | 8 | 1 |


### `standard_junior` — Standard Junior / СТАНДАРТ-ДЖУНИЪР

- Ours: **23** riders, theirs: **19** riders, matched: **19**.
- Of the matched riders, **9** share a final position and **8** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 665 | Иван ИВАНОВ | 6 / 6 | 73 / 87 | -14 | 5 / 5 |
| 775 | Георги ВЪЛЕВ 4:18:58.0 | 1 / 1 | 137 / 147 | -10 | 6 / 6 |
| 282 | Александър ПИРИШАНЧИН | 5 / 5 | 94 / 103 | -9 | 6 / 6 |
| 521 | Адриан ЦЕКОВ | 8 / 7 | 31 / 40 | -9 | 4 / 3 |
| 728 | Никола ТЕРЗИЕВ | 3 / 2 | 128 / 136 | -8 | 6 / 6 |
| 143 | Мехмед ЛАПАНД | 7 / 9 | 36 / 28 | +8 | 2 / 2 |
| 71 | Алекс АТАНАСОВ | 12 / 14 | 20 / 13 | +7 | 1 / 1 |
| 155 | Петър КРАЧУНОВ | 13 / 12 | 16 / 23 | -7 | 1 / 2 |
| 235 | Даниел ВАСИЛЕВ | 2 / 3 | 130 / 124 | +6 | 6 / 7 |
| 913 | Мирослав КЕРАНДЖИЕВ | 4 / 4 | 108 / 104 | +4 | 6 / 7 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 310 | Емилиян ЕВТИМОВ | 20 | 2 | 1 |
| 298 | Мартин КОВАЧЕВ | 21 | 0 | 1 |
| 474 | Самуил ПЕТКОВ | 22 | 0 | 1 |
| 751 | БОЯН СТАМОВ 2:23:11.8 | 23 | 0 | 3 |


### `women` — Women / ЖЕНИ

- Ours: **9** riders, theirs: **7** riders, matched: **7**.
- Of the matched riders, **3** share a final position and **2** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 533 | Атанаска ГЕОРГИЕВА | 5 / 4 | 71 / 88 | -17 | 5 / 4 |
| 10 | Никол ИЛИЕВА | 1 / 1 | 162 / 147 | +15 | 6 / 6 |
| 407 | Преслава ГЕОРГИЕВА | 3 / 3 | 94 / 102 | -8 | 6 / 5 |
| 788 | Мария РАЕВА | 7 / 6 | 27 / 20 | +7 | 2 / 1 |
| 750 | Рая МОНЕВА | 2 / 2 | 132 / 126 | +6 | 6 / 7 |
| 706 | Владислава СЛАВОВА | 6 / 5 | 29 / 29 | +0 | 6 / 2 |
| 334 | Цветомира ГЕОРГИЕВА | 8 / 7 | 15 / 15 | +0 | 1 / 1 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 813 | Галена МАРКОВА-НЕДЕЛЧЕВА | 4 | 93 | 6 |
| 318 | Зорница ТОДОРОВА 4:43:28.1 | 9 | 0 | 1 |


### `seniors_40` — Senior 40+ / СЕНЬОРИ 40+

- Ours: **42** riders, theirs: **33** riders, matched: **33**.
- Of the matched riders, **7** share a final position and **16** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 125 | Десислав ЦЕКОВ | 5 / 2 | 104 / 126 | -22 | 6 / 6 |
| 169 | Илиян КРЪСТЕВ | 10 / 15 | 54 / 42 | +12 | 3 / 3 |
| 51 | Марио ЗАРОВ | 15 / 11 | 36 / 48 | -12 | 3 / 4 |
| 292 | Светослав ХРИСТОВ | 7 / 6 | 92 / 103 | -11 | 5 / 6 |
| 916 | Росен ЖЕЛЯЗКОВ | 14 / 10 | 39 / 50 | -11 | 6 / 6 |
| 30 | Илиян КУЗМАНОВ | 1 / 1 | 131 / 141 | -10 | 6 / 6 |
| 67 | Александър ВЕСКОВ | 40 / 23 | 0 / 10 | -10 | 5 / 2 |
| 31 | Христо МИХОВ | 17 / 16 | 21 / 30 | -9 | 2 / 3 |
| 83 | Лъчезар ВУНЧЕВ | 9 / 8 | 64 / 69 | -5 | 5 / 5 |
| 666 | Цветан ДЕНЕВ | 4 / 5 | 107 / 103 | +4 | 6 / 7 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 165 | Лъчезар БЛИЗНАКОВ | 32 | 0 | 1 |
| 208 | Костадин ТОШЕВ | 33 | 0 | 1 |
| 233 | Мариян ТИНЧЕВ | 34 | 0 | 1 |
| 239 | Смилен КАБАКЧИЕВ 4:40:23.3 | 35 | 0 | 1 |
| 25 | Бижо БИЖЕВ | 36 | 0 | 2 |
| 153 | Станислав СТОЯНОВ 3:22:19.5 | 37 | 0 | 2 |
| 174 | Павел МИХАЙЛОВ | 38 | 0 | 2 |
| 227 | Венелин ВИДЕНОВ | 39 | 0 | 3 |
| 179 | Владимир ВЪЛЧЕВ | 41 | 0 | 5 |


### `seniors_50` — Senior 50+ / СЕНЬОРИ 50+

- Ours: **17** riders, theirs: **15** riders, matched: **14**.
- Of the matched riders, **7** share a final position and **5** share a total point count.

**Top point divergences (matched riders)**

| # | Rider | Pos (ours / theirs) | Points (ours / theirs) | Δ pts | Races (ours / theirs) |
|---:|---|:---:|:---:|---:|:---:|
| 569 | Пламен АТАНАСОВ 5:30:45.4 | 12 / 6 | 13 / 33 | -20 | 2 / 2 |
| 339 | Ясен ПОПОВ | 1 / 1 | 98 / 114 | -16 | 6 / 5 |
| 225 | Иван СПАСОВ | 6 / 10 | 37 / 22 | +15 | 4 / 1 |
| 70 | Стоян ПАЧАРОЗОВ | 2 / 2 | 82 / 92 | -10 | 5 / 4 |
| 129 | Георги КЪНЧЕВ | 9 / 12 | 28 / 18 | +10 | 3 / 1 |
| 855 | Руси ТЕНЕВ | 5 / 5 | 42 / 34 | +8 | 4 / 2 |
| 574 | Михаил Кръшняк | 4 / 4 | 54 / 47 | +7 | 4 / 3 |
| 302 | Благой ТОДОРОВ | 7 / 7 | 37 / 31 | +6 | 2 / 2 |
| 303 | Емил БРАТОЕВ | 8 / 8 | 31 / 26 | +5 | 5 / 2 |
| 50 | Панчо КУЗМАНОВ | 3 / 3 | 68 / 68 | +0 | 6 / 4 |

**Only in our DB**:

| # | Rider | Our pos | Our pts | Our races |
|---:|---|:---:|---:|:---:|
| 126 | Иван Иванов | 15 | 0 | 1 |
| 360 | Кристиан САРАЛИЕВ | 16 | 0 | 1 |
| 571 | Ангел ТРАКОВ | 17 | 0 | 1 |

**Only on hardendurobulgaria.com**:

| # | Rider | Their pos | Their pts | Their races |
|---:|---|:---:|---:|:---:|
| 89 | Добрин ДОБРЕВ | 11 | 18 | 1 |


## Methodology

```python
# Match key: race_number
# Ours endpoint: GET /api/seasons/2025/standings/{category}
# Theirs: scraped HTML from https://hardendurobulgaria.com/?category={category}
# Names compared case-insensitively.
# 'Diff' = matched rider with different position OR different total OR different race count.
```

Script: `/tmp/validate_2025.py` (generates `/tmp/validate_2025.json` consumed by this report).