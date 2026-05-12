"""Print a diff between the old per-day-sum scoring and the new combined-
time scoring for every (event, category, rider) in 2026.

Old policy: event_points = Σ EventResult.points across days (raw CSV).
New policy: rank eligible riders by Σ time_ms, award from 25/22/20/… table.

Run from backend/:
    python -m scripts.scoring_diff_2026 > ../.reports/2026-scoring-diff.md
"""

from __future__ import annotations

from sqlalchemy import select

from src.db import get_session
from src.db.models import Category, Event, EventResult, Rider, Season
from src.services.scoring import compute_event_scoring


def _fmt_time(ms: int | None) -> str:
    if ms is None:
        return "—"
    s, cs = divmod(int(ms), 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}.{cs // 100}"


def main() -> None:
    with get_session() as session:
        season = session.execute(select(Season).where(Season.year == 2026)).scalar_one()
        events = session.execute(
            select(Event).where(Event.season_id == season.id).order_by(Event.sort_order)
        ).scalars().all()
        cats = session.execute(
            select(Category).where(Category.season_id == season.id).order_by(Category.sort_order)
        ).scalars().all()

        print(f"# Scoring policy diff — {season.year}")
        print()
        print("**Old policy:** sum of per-day CSV `points` per (rider, event).  ")
        print("**New policy:** combined-time ranking with tier-based fallback.")
        print()
        print("Points tables:")
        print()
        print("- 1-day events (max 25): 25,22,20,18,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1")
        print("- 2-day events (max 40): 40,34,30,27,24,22,20,18,16,14,12,10,8,7,6,5,4,3,2,1")
        print()
        print("Ranking for 2-day events:")
        print()
        print("1. Full finishers (`FIN` both days) — sorted by sum of `time_ms`.")
        print("2. Day-1-only finishers — sorted by day-1 `time_ms`, placed below every Tier 1 rider.")
        print("3. Day-2-only finishers — sorted by day-2 `time_ms`, placed below every Tier 2 rider.")
        print()
        print("Riders with no FIN at all get 0 points, no position.")
        print()
        print("Single-day events (Kyrnare 2026) are unaffected: ranking by day-1")
        print("time reproduces the CSV's positions and 25/22/… points.")
        print()
        print("Detailed deltas follow, grouped by race + category, then a")
        print("season-totals view at the bottom. The `tier` column shows 1/2/3")
        print("for 2-day events; — for ineligible riders.")
        print()

        season_totals_old: dict[tuple[int, int], float] = {}  # (cat_id, rider_id) → pts
        season_totals_new: dict[tuple[int, int], float] = {}

        for ev in events:
            for cat in cats:
                # All EventResult rows for this (event, category).
                rows = session.execute(
                    select(EventResult)
                    .join(Rider, EventResult.rider_id == Rider.id)
                    .where(EventResult.event_id == ev.id, Rider.category_id == cat.id)
                ).scalars().all()
                if not rows:
                    continue

                by_rider: dict[int, list[EventResult]] = {}
                for r in rows:
                    by_rider.setdefault(r.rider_id, []).append(r)

                new_scores = compute_event_scoring(rows)

                lines: list[tuple[int, str]] = []
                changes = 0
                for rider_id, rider_rows in by_rider.items():
                    rider = rider_rows[0].rider
                    old_pts = sum(float(r.points or 0) for r in rider_rows)
                    new_pts = new_scores[rider_id].points
                    new_pos = new_scores[rider_id].combined_position
                    new_time = new_scores[rider_id].combined_time_ms

                    by_day = {(r.day or 1): r for r in rider_rows}
                    d1 = by_day.get(1)
                    d2 = by_day.get(2)
                    d1_time = (d1.time_ms if d1 and (d1.status or "").upper() == "FIN" else None)
                    d2_time = (d2.time_ms if d2 and (d2.status or "").upper() == "FIN" else None)

                    season_totals_old[(cat.id, rider_id)] = (
                        season_totals_old.get((cat.id, rider_id), 0) + old_pts
                    )
                    season_totals_new[(cat.id, rider_id)] = (
                        season_totals_new.get((cat.id, rider_id), 0) + new_pts
                    )

                    if old_pts == new_pts:
                        continue
                    changes += 1
                    delta = new_pts - old_pts
                    tier = new_scores[rider_id].tier
                    name = f"#{rider.race_number} {rider.first_name} {rider.last_name}"
                    pos_str = str(new_pos) if new_pos is not None else "—"
                    tier_str = str(tier) if tier is not None else "—"
                    d1_str = _fmt_time(d1_time) if d1_time is not None else (
                        (d1.status if d1 else None) or "—"
                    )
                    d2_str = _fmt_time(d2_time) if d2_time is not None else (
                        (d2.status if d2 else None) or "—"
                    )
                    lines.append((
                        new_pos if new_pos is not None else 999,
                        f"| {pos_str:>3} | {tier_str:>4} | {name:<40} | {old_pts:>5.0f} | {new_pts:>5.0f} | {delta:>+5.0f} | {d1_str:>10} | {d2_str:>10} | {_fmt_time(new_time):>10} |",
                    ))

                if not changes:
                    continue
                lines.sort(key=lambda x: x[0])
                print(f"## {ev.name} — {cat.display_name}")
                print()
                print(f"_{changes} rider(s) with a points change._")
                print()
                print("| pos | tier | rider | old | new | Δ | day 1 | day 2 | total |")
                print("|----:|-----:|-------|----:|----:|--:|------:|------:|------:|")
                for _, line in lines:
                    print(line)
                print()

        # Season-total deltas per category.
        print("# Season totals — riders with a delta")
        print()
        for cat in cats:
            rows: list[tuple[float, str]] = []
            for (cat_id, rider_id), new_total in season_totals_new.items():
                if cat_id != cat.id:
                    continue
                old_total = season_totals_old.get((cat_id, rider_id), 0)
                if old_total == new_total:
                    continue
                rider = session.get(Rider, rider_id)
                rows.append((
                    -new_total,
                    f"| #{rider.race_number} {rider.first_name} {rider.last_name} | {old_total:.0f} | {new_total:.0f} | {new_total - old_total:+.0f} |",
                ))
            if not rows:
                continue
            rows.sort(key=lambda x: x[0])
            print(f"## {cat.display_name}")
            print()
            print("| rider | old total | new total | Δ |")
            print("|-------|----------:|----------:|--:|")
            for _, line in rows:
                print(line)
            print()


if __name__ == "__main__":
    main()
