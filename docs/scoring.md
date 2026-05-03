# Scoring policy

This document explains how the BGX dashboard computes standings, and why the numbers may differ from other sources (notably hardendurobulgaria.com).

## TL;DR

We are an **archive of every result** the championship publishes, not a faithful mirror of the official scoring. Three deliberate choices drive the differences:

1. **Multi-day events sum cumulatively.** A two-day weekend (Gorna Malina, Botevgrad, etc.) is one `Event`, but every day's results are imported. The points for that event are the sum of every day's points for the rider.
2. **No drop-worst rule.** Some championships discard a rider's worst result when they have 7+ events. We do not. Every race counts.
3. **Some races are not imported.** 2025 Six Days, for example, is not in our dataset. The `events` list per season is the source of truth.

Riders who registered but did not finish a day appear with 0 points. They are kept in the leaderboard for the audit trail.

## Tiebreakers

When two riders end the season tied on `total_points`, the season leaderboard breaks the tie in this order:

1. **Better best-position wins.** The lowest single-race finish on the rider's record. A 1st-place finish anywhere in the season beats a season of 5th-place finishes.
2. **Higher inverse-position sum wins.** Per event the rider entered, score = `(finishers_in_event_category − rider_position + 1) / finishers_in_event_category`. Each event contributes a value in (0, 1]: 1.0 for an event win, ~0 for last finisher. DNF / DNS / DSQ / events with no real position data contribute 0. Sum across every event. Higher = better. This rewards "more races + better finishes" together — a rider who showed up to 5 races and finished mid-pack each time outranks a rider who showed up to 1 race and finished mid-pack once. Field size is normalized into the formula so a 5-of-25 finish in a small race isn't drowned out by a 30-of-125 finish in a big one.
3. **Lower race number wins.** Final, deterministic break.

The inverse-position score is computed silently — it is never exposed over the API and never displayed in the UI. It exists purely to give the bottom of the leaderboard a sensible ordering.

This rule applies the same way to riders with 0 total points (a large group — in the 2025 `standard` category, 91 of 142 riders end the season scoreless). They all share `best-position = 21` (imputed from 0 points), so the inverse-position sum is what actually orders the tail of the table by their race-day results.

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
