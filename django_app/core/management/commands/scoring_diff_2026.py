"""X4 — ``manage.py scoring_diff_2026`` — Django port of
``backend/scripts/scoring_diff_2026.py``.

Prints a diff between the old per-day-sum scoring and the new combined-time
scoring for every (event, category, rider) in 2026. The report-building
logic (formatting, tier columns, season-totals view, sort keys) is reused
**VERBATIM** — only the data access is rewritten:

* ``from src.services.scoring import compute_event_scoring`` →
  ``from core.services.scoring import compute_event_scoring`` (S2's port;
  same pure-Python algorithm, consumed read-only — X4 acceptance
  criterion: the report depends on the S2 scoring service).
* ``session.execute(select(Season).where(...)).scalar_one()`` →
  ``Season.objects.get(year=2026)``
* ``select(EventResult).join(Rider, ...).where(EventResult.event_id == ev.id,
  Rider.category_id == cat.id)`` →
  ``EventResult.objects.filter(event_id=ev.id,
  rider__category_id=cat.id).select_related("rider")``. ``select_related``
  is added so ``r.rider`` is the SAME single-query attribute access the
  SQLAlchemy relationship gave (``r.rider.race_number`` etc.) — no
  behavioral change, just avoids N+1.
* ``session.get(Rider, rider_id)`` → ``Rider.objects.get(pk=rider_id)``.
* ``compute_event_scoring`` is called with the ORM rows exactly as before;
  it duck-types ``rider_id``/``day``/``status``/``time_ms`` so the Django
  rows are accepted unchanged (proven by S2's module contract).

Floats: the SQLAlchemy ``EventResult.points`` was a numeric coerced via
``float(r.points or 0)``; Django returns ``Decimal``. ``float(...)`` is
applied at the exact same call sites the original used, so the printed
output is byte-identical.

Original docstring (preserved verbatim) ---------------------------------------

Print a diff between the old per-day-sum scoring and the new combined-
time scoring for every (event, category, rider) in 2026.

Old policy: event_points = Σ EventResult.points across days (raw CSV).
New policy: rank eligible riders by Σ time_ms, award from 25/22/20/… table.

Run:
    python manage.py scoring_diff_2026 > ../.reports/2026-scoring-diff.md
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import Category, Event, EventResult, Rider, Season
from core.services.scoring import compute_event_scoring


def _fmt_time(ms: int | None) -> str:
    if ms is None:
        return "—"
    s, cs = divmod(int(ms), 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}.{cs // 100}"


def scoring_diff_2026(*, stdout=None) -> None:
    def p(msg: str = "") -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    season = Season.objects.get(year=2026)
    events = list(
        Event.objects.filter(season_id=season.id).order_by("sort_order")
    )
    cats = list(
        Category.objects.filter(season_id=season.id).order_by("sort_order")
    )

    p(f"# Scoring policy diff — {season.year}")
    p()
    p("**Old policy:** sum of per-day CSV `points` per (rider, event).  ")
    p("**New policy:** combined-time ranking with tier-based fallback.")
    p()
    p("Points tables:")
    p()
    p("- 1-day events (max 25): 25,22,20,18,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1")
    p("- 2-day events (max 40): 40,34,30,27,24,22,20,18,16,14,12,10,8,7,6,5,4,3,2,1")
    p()
    p("Ranking for 2-day events:")
    p()
    p("1. Full finishers (`FIN` both days) — sorted by sum of `time_ms`.")
    p("2. Day-1-only finishers — sorted by day-1 `time_ms`, placed below every Tier 1 rider.")
    p("3. Day-2-only finishers — sorted by day-2 `time_ms`, placed below every Tier 2 rider.")
    p()
    p("Riders with no FIN at all get 0 points, no position.")
    p()
    p("Single-day events (Kyrnare 2026) are unaffected: ranking by day-1")
    p("time reproduces the CSV's positions and 25/22/… points.")
    p()
    p("Detailed deltas follow, grouped by race + category, then a")
    p("season-totals view at the bottom. The `tier` column shows 1/2/3")
    p("for 2-day events; — for ineligible riders.")
    p()

    season_totals_old: dict[tuple[int, int], float] = {}  # (cat_id, rider_id) → pts
    season_totals_new: dict[tuple[int, int], float] = {}

    for ev in events:
        for cat in cats:
            # All EventResult rows for this (event, category).
            rows = list(
                EventResult.objects.filter(
                    event_id=ev.id, rider__category_id=cat.id
                ).select_related("rider")
            )
            if not rows:
                continue

            by_rider: dict[int, list[EventResult]] = {}
            for r in rows:
                by_rider.setdefault(r.rider_id, []).append(r)

            new_scores = compute_event_scoring(rows)

            # Old-policy position: rank riders within (event, category) by
            # the sum of their CSV points, descending. Riders with 0 points
            # get no position (they didn't earn anything under the old
            # rules either). Ties broken by race_number ascending so the
            # output is stable across runs.
            old_pts_by_rider: dict[int, float] = {
                rid: sum(float(r.points or 0) for r in rs)
                for rid, rs in by_rider.items()
            }
            ranked_old = sorted(
                [rid for rid, pts in old_pts_by_rider.items() if pts > 0],
                key=lambda rid: (
                    -old_pts_by_rider[rid],
                    by_rider[rid][0].rider.race_number,
                ),
            )
            old_pos_by_rider: dict[int, int] = {
                rid: i + 1 for i, rid in enumerate(ranked_old)
            }

            lines: list[tuple[int, str]] = []
            changes = 0
            for rider_id, rider_rows in by_rider.items():
                rider = rider_rows[0].rider
                old_pts = old_pts_by_rider[rider_id]
                new_pts = new_scores[rider_id].points
                new_pos = new_scores[rider_id].combined_position
                old_pos = old_pos_by_rider.get(rider_id)
                new_time = new_scores[rider_id].combined_time_ms

                by_day = {(r.day or 1): r for r in rider_rows}
                d1 = by_day.get(1)
                d2 = by_day.get(2)
                d1_time = (
                    d1.time_ms
                    if d1 and (d1.status or "").upper() == "FIN"
                    else None
                )
                d2_time = (
                    d2.time_ms
                    if d2 and (d2.status or "").upper() == "FIN"
                    else None
                )

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
                new_pos_str = str(new_pos) if new_pos is not None else "—"
                old_pos_str = str(old_pos) if old_pos is not None else "—"
                if old_pos is not None and new_pos is not None:
                    pos_delta = new_pos - old_pos
                    pos_delta_str = f"{pos_delta:+d}" if pos_delta != 0 else "0"
                else:
                    pos_delta_str = "—"
                tier_str = str(tier) if tier is not None else "—"
                d1_str = _fmt_time(d1_time) if d1_time is not None else (
                    (d1.status if d1 else None) or "—"
                )
                d2_str = _fmt_time(d2_time) if d2_time is not None else (
                    (d2.status if d2 else None) or "—"
                )
                lines.append((
                    new_pos if new_pos is not None else 999,
                    f"| {new_pos_str:>3} | {old_pos_str:>3} | {pos_delta_str:>4} | {tier_str:>4} | {name:<40} | {new_pts:>5.0f} | {old_pts:>5.0f} | {delta:>+5.0f} | {d1_str:>10} | {d2_str:>10} | {_fmt_time(new_time):>10} |",
                ))

            if not changes:
                continue
            lines.sort(key=lambda x: x[0])
            p(f"## {ev.name} — {cat.display_name}")
            p()
            p(f"_{changes} rider(s) with a points change._")
            p()
            p("| new pos | old pos | Δ pos | tier | rider | new pts | old pts | Δ pts | day 1 | day 2 | total |")
            p("|--------:|--------:|------:|-----:|-------|--------:|--------:|------:|------:|------:|------:|")
            for _, line in lines:
                p(line)
            p()

    # Season-total deltas per category.
    p("# Season totals — riders with a delta")
    p()
    for cat in cats:
        rows: list[tuple[float, str]] = []
        for (cat_id, rider_id), new_total in season_totals_new.items():
            if cat_id != cat.id:
                continue
            old_total = season_totals_old.get((cat_id, rider_id), 0)
            if old_total == new_total:
                continue
            rider = Rider.objects.get(pk=rider_id)
            rows.append((
                -new_total,
                f"| #{rider.race_number} {rider.first_name} {rider.last_name} | {old_total:.0f} | {new_total:.0f} | {new_total - old_total:+.0f} |",
            ))
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        p(f"## {cat.display_name}")
        p()
        p("| rider | old total | new total | Δ |")
        p("|-------|----------:|----------:|--:|")
        for _, line in rows:
            p(line)
        p()


class Command(BaseCommand):
    help = (
        "Print the old-vs-new scoring policy diff for the 2026 season "
        "(consumes the S2 compute_event_scoring service)."
    )

    def handle(self, *args, **options):
        scoring_diff_2026(stdout=self.stdout)
