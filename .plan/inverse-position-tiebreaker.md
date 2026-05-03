# Inverse-position tiebreaker for season standings

<!-- Source design doc: ~/.gstack/projects/k-ivanov-bgx-leaderboard/konstantinivanov-development-design-20260503-234948.md (APPROVED 2026-05-03) -->

## Context

The season leaderboard's tail is essentially noise. After sorting by
`total_points` and `best_position`, the existing tiebreaker is **fewer races
wins** (`races_participated` ascending), then **lower race number wins**. In
the `standard` category 91 of 142 riders end the season with 0 total points —
all sit at the same `best_position = 21` (imputed from 0 points), so the
"fewer races wins" rule decides who's listed where. A rider who entered 1
race and finished 25th-of-60 ranks above a rider who entered 7 races and
finished 25th-of-60 in every one. That's the opposite of how competitive
enduro feels.

We have rich per-race data even for 0-pointers: 309/309 zero-point rows in
2025 carry explicit `position`, `time_ms`, `gap_ms`, `status`. We just
aren't using any of it for ordering.

This change replaces the broken `races_participated` slot in the sort key
with an aggregate `total_inverse_position` score, computed across every
event the rider entered. Higher = better. Applied everywhere ties occur,
not only at the 0-point tail.

## Algorithm (one paragraph)

Per event, per rider: `shadow = (finishers_in_event_category − rider_position + 1) / finishers_in_event_category`
where `rider_position` comes from the rider's best (lowest) day in that
event, and `finishers_in_event_category` counts `EventResult` rows for that
`(event, category)` with non-null `position`. Each event contributes a
value in (0, 1]: 1.0 for the win, ~1/finishers for last. DNF / DNS / DSQ /
imputed-from-points → 0. Sum across all the rider's events to get
`total_inverse_position`. Slot it into the sort key in place of
`races_participated`:

```python
# before
key=lambda r: (-r.total_points, r.best_position, r.races_participated, r.rider.race_number)
# after
key=lambda r: (-r.total_points, r.best_position, -r.total_inverse_position, r.rider.race_number)
```

`races_participated` is still surfaced as a `StandingsRow` field, just
not in the sort key.

## Worked example (60-rider field)

Per-event contribution = `(60 − position + 1) / 60`.

| Rider | Finishes | Old order | `total_inverse_position` | New order |
|---|---|---|---|---|
| X | 25, 25, 25 | wins (3 races) | 0.60 × 3 = **1.80** | 2nd |
| Y | 50, 50, 50, 50, 50 | loses (5 races) | 0.18 × 5 = **0.92** | 3rd |
| Z | 25, 25, 25, 30, 35 | loses (5 races) | 0.60 × 3 + 0.52 + 0.43 = **2.75** | 1st |

Old: X › Y › Z. New: Z › X › Y. New order matches "more races + better
finishes wins."

## Tasks

### 1. Verify premise — field-size variance check ✅ DONE

Coefficient of variation (stddev / mean) of finisher counts per
(event, category) across 2024–2026 prod data:

| Category | CV | Range |
|---|---|---|
| expert | 0.36 | 16–58 |
| profi | 0.47 | 2–18 |
| seniors_40 | 0.39 | 12–31 |
| seniors_50 | 0.61 | 2–17 |
| standard | 0.43 | 25–125 |
| standard_junior | 0.54 | 4–22 |
| women | 0.59 | 2–11 |

Every category exceeds the 0.30 threshold; `standard` runs from 25 to 125
finishers in the same season. Raw inverse position would let big races
dominate. **Decision: use option B (percentile)** — already reflected in
the algorithm + tests + docs above.

### 2. Implement in `backend/src/services/standings.py` ✅ DONE

- [x] Added `total_inverse_position: float` to the `StandingsRow` dataclass.
- [x] Built a `finishers_per_event: dict[int, int]` lookup once, in-memory
  from the already-loaded `Rider.results`, taking the max across days for
  multi-day events. No extra SQL.
- [x] Per-event contribution computed inside the existing collapsing block;
  imputed positions contribute 0; clamped to [0, 1].
- [x] Replaced `r.races_participated` with `-r.total_inverse_position` in
  the sort key. `race_number` stays as the final stable break.
- [x] Comment block above the sort updated; points at `docs/scoring.md`
  for the rationale.

### 3. Update tests ✅ DONE

- [x] `backend/tests/test_standings_tiebreakers.py` — rewritten end-to-end
  to mirror the new sort key. `test_fewer_races_breaks_ties_after_best_position`
  removed. `test_inverse_position_sum_breaks_ties` added with the worked
  example. `test_realistic_full_chain` updated.
- [x] `backend/tests/test_standings_inverse_position.py` (NEW) — four
  integration tests against seeded data:
  - `test_inverse_position_is_in_unit_interval_per_event` — formula sanity.
  - `test_winners_have_highest_inverse_position` — top of leaderboard
    correlates with high inverse-position sum.
  - `test_inverse_position_is_active_tiebreaker_after_best_position` —
    within (total_points, best_position) ties, inverse-position decides.
  - `test_dnf_or_imputed_position_contributes_zero` — riders with no
    explicit position rows contribute 0.
- [x] Full backend suite: 109 → **112 passed** (+1 replaced, +4 added).

### 4. Documentation ✅ DONE

- [x] `docs/scoring.md`: "Tiebreakers" section confirms the percentile
  formula that actually shipped; reference list under "How to change the
  policy" updated with the tiebreakers entry.
- [x] `backend/CLAUDE.md` — no tiebreaker references; nothing to sync.
- [x] `standings.py` top-of-file comment — scoring policy only, no
  tiebreaker references; lower comment block above the sort key was
  rewritten as part of task 2.

### 5. Verify on local dev

- [ ] Start local backend + frontend (`docker compose up -d postgres &&
  cd backend && ./start.sh` then `cd frontend && npm run dev`).
- [ ] Open `/results?season=2025&category=standard`, scroll to the bottom.
- [ ] Eyeball the tail: does the new ordering match intuition? A rider
  who showed up to 5 races and finished mid-pack each time should be
  visibly above a rider who showed up to 1 race.
- [ ] Diff the bottom-20 ordering vs prod (`https://hardendurobulgaria.com/results?season=2025&category=standard`)
  — different is expected and good.

### 6. Ship

- [ ] Commit with the standard prefix: `feat(standings): inverse-position
  tiebreaker replaces "fewer races wins"`.
- [ ] Push to `main`. CI runs the full pytest suite plus the openapi
  drift check.
- [ ] After GHA release.yml succeeds, redeploy: `railway redeploy
  --service bgx-leaderboard --from-source --yes`.

## Critical files

| File | Action |
|---|---|
| `backend/src/services/standings.py` | Modify — new field, new lookup dict, sort-key swap, comment update |
| `backend/tests/test_standings_tiebreakers.py` | Replace one test, add two tests |
| `backend/tests/test_standings_2025.py` | Re-snap (expected) |
| `docs/scoring.md` | Add Tiebreakers section (companion edit in this PR) |

## Out of scope

- API surface changes — `total_inverse_position` stays internal, never
  serialized into `StandingsRowOut`.
- UI changes — the score is invisible per design.
- Tiebreaker behavior for ties WITHIN an event (e.g., two riders sharing
  position 1 in a race). Today that's the importer's job; nothing changes.
- Drop-worst rule for non-2025 seasons (separate, larger change tracked
  in `docs/scoring.md` "How to change the policy").

## Success criteria

- Backend test suite stays green; 2+ new tests added.
- Top of every category leaderboard unchanged.
- Bottom of `standard` category visibly re-ordered to favor riders with
  more races + better finishes.
- Zero schema migrations, zero API contract changes, zero UI work.
