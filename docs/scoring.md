# Scoring policy

This document explains how the BGX dashboard computes standings, and why the numbers may differ from other sources (notably hardendurobulgaria.com).

## TL;DR

We are an **archive of every result** the championship publishes, not a faithful mirror of the official scoring. Three deliberate choices drive the differences:

1. **Multi-day events are scored by combined time, with partial-finisher fallback.** A two-day weekend (Gorna Malina, Botevgrad, etc.) is one `Event` with every day's results imported. Points come from a position table whose maximum scales with the number of days:
   - **1-day events** (max 25): `25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1` for positions 1–20, 0 below.
   - **2-day events** (max 40): `40, 34, 30, 27, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1` (sum of the day-1 and day-2 scales at matching positions).

   Ranking for a 2-day event proceeds in three tiers, each sorted ascending by time, and positions count across tiers (a Tier-2 rider in position 21+ earns 0, same as Tier 1):
   1. **Full finishers** (`FIN` + positive `time_ms` on every day) — ranked by sum of `time_ms`.
   2. **Day-1-only finishers** — ranked by day-1 `time_ms`. Placed below every Tier-1 rider.
   3. **Day-2-only finishers** — ranked by day-2 `time_ms`. Placed below every Tier-2 rider.

   Day-1 has priority over day-2 by design — finishing the opening day is harder to recover from missing. Riders with no `FIN` on any day get 0 points and no position. Implemented in [`backend/src/services/scoring.py`](../backend/src/services/scoring.py).
2. **No drop-worst rule.** Some championships discard a rider's worst result when they have 7+ events. We do not. Every race counts.
3. **Some races are not imported.** 2025 Six Days, for example, is not in our dataset. The `events` list per season is the source of truth.

Riders who registered but did not finish a day appear with 0 points. They are kept in the leaderboard for the audit trail.

## Tiebreakers

When two riders end the season tied on `total_points`, the season leaderboard breaks the tie in this order:

1. **Riders with at least one real finish rank above riders who only DNF/DNS-ed.** A rider whose every event was DNF / DNS / DSQ has their `best_position` imputed from points (0 pts → 21). Without this rule, a back-of-pack 23rd-place finish would lose to a never-finished rider whose imputed best is 21. Anyone who actually finished a race outranks anyone who never did.
2. **Better best-position wins.** Within each tier above, the lowest single-race finish on the rider's record. A 1st-place finish anywhere in the season beats a season of 5th-place finishes.
3. **Higher inverse-position sum wins.** Per event the rider entered, score = `(finishers_in_event_category − rider_position + 1) / finishers_in_event_category`. Each event contributes a value in (0, 1]: 1.0 for an event win, ~0 for last finisher. DNF / DNS / DSQ / events with no real position data contribute 0. Sum across every event. Higher = better. This rewards better finishes — and rewards more of them, since each finish adds to the sum. Field size is normalized into the formula so a 5-of-25 finish in a small race isn't drowned out by a 30-of-125 finish in a big one.
4. **More races participated wins.** Among riders tied on everything above (typically the all-DNF group, where the inverse-position sum is 0 for everyone), the rider who entered more events ranks higher. "Showed up 3 times and DNF'd" beats "showed up once and DNF'd."
5. **Lower race number wins.** Final, deterministic break.

The inverse-position score and the imputed-only flag are computed silently — neither is exposed over the API or rendered in the UI. They exist purely to give the bottom of the leaderboard a sensible ordering.

This rule applies the same way to riders with 0 total points (a large group — in the 2025 `standard` category, 91 of 142 riders end the season scoreless). The rider tiers split first by who finished anything at all; within each tier the inverse-position sum and races-participated counts decide the rest.

## How it differs from hardendurobulgaria.com

For the 2025 season, hardendurobulgaria.com:

- Counts only day-1 results (their banner: "Results from first navigation day").
- Drops the worst result when a rider has 7 events.
- Includes Six Days as a championship round.
- Filters out riders with zero points.

A full row-by-row comparison lives at `.reports/2025-validation-vs-hardendurobulgaria.md`. Match rate on rider identity (race number + name) is ~95% per category; the point totals differ for the reasons above.

## How to change the policy

If the championship rules change, or if you want a faithful mirror of the official scoring, the relevant code is:

- **Multi-day sum** — `backend/src/services/standings.py`. The query that sums `EventResult.points` per `(rider, event)` does not filter by `EventResult.day`.
- **Drop-worst** — Not implemented. Add a `championship_format` enum value (currently only `per_event` exists) on `Season` (`backend/src/db/models.py`) and branch in `services/standings.py`.
- **Race set** — Curated by which CSVs land in `seed_data/`. To add a missing race, drop the CSV in the right year folder and run `make seed-new`.
- **Tiebreakers** — `backend/src/services/standings.py`, the sort-key block at the bottom of `get_standings()`. Pinned by `tests/test_standings_tiebreakers.py`. The current chain is documented in the **Tiebreakers** section above; flipping any link in the chain requires updating both the test and that section.

## Why we keep this (instead of mirroring)

A complete archive is more useful long-term: if the championship rules change retroactively, our raw data lets us replay any new scoring policy. A mirror would force us to re-import every season.

The trade-off is that the public-facing leaderboards on `bgx.…` will not exactly match other sources during the season. The validation report makes the deltas explicit; the docs link to it; the point totals are accurate to our archive.

## Pointers

- Raw results: any leaderboard page (`/{year}/{category}`) — sortable, filterable, exportable.
- Validation: `.reports/2025-validation-vs-hardendurobulgaria.com.md`.
- Scoring code: `backend/src/services/standings.py`.
- Schema: `backend/src/db/models.py` — see `Season`, `Category`, `Event`, `EventResult`, `Rider`.
