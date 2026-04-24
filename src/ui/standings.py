"""Season standings table for a category."""

from fasthtml.common import (
    A,
    Div,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)

from .common import position_badge, score_cell


def _rider_link(year: int, rider):
    # URL-safe-ish slug that pairs with the /r/{race_number}/{slug} route.
    slug = f"{rider.first_name.strip()}-{rider.last_name.strip()}".replace(" ", "-").lower()
    return f"/{year}/r/{rider.race_number}/{slug}"


def _event_header(year: int, category_code: str, event):
    return A(event.name, href=f"/{year}/{category_code}/{event.slug}", cls="event-link")


def standings_table(*, year: int, category, events, standings_rows, championship_format: str):
    has_drop = championship_format == "aggregate_2025"

    headers = [
        Th("#", cls="center"),
        Th("No.", cls="center"),
        Th("Rider"),
        Th("Total", cls="num"),
        Th("Raced", cls="center"),
        Th("Best", cls="center"),
    ]
    if has_drop:
        headers.append(Th("Dropped", cls="center"))
    headers.extend(
        [Th(_event_header(year, category.code, ev), cls="num") for ev in events]
    )

    rows = []
    for row in standings_rows:
        rider_href = _rider_link(year, row.rider)
        cells = [
            Td(position_badge(row.final_position), cls="center"),
            Td(
                A(str(row.rider.race_number), href=rider_href, cls="mono"),
                cls="center",
            ),
            Td(
                A(
                    f"{row.rider.first_name} {row.rider.last_name}",
                    href=rider_href,
                    cls="rider-name",
                ),
                Div(row.rider.team or "", cls="rider-meta") if row.rider.team else None,
            ),
            Td(Span(_fmt_total(row.total_points), cls="mono"), cls="num"),
            Td(str(row.races_participated), cls="center"),
            Td(str(row.best_position), cls="center"),
        ]
        if has_drop:
            if row.worst_dropped is None:
                cells.append(Td(Span("—", cls="score-dim"), cls="center"))
            else:
                cells.append(
                    Td(
                        Span(f"−{_fmt_points(row.worst_dropped)}", cls="score-dim"),
                        cls="center mono",
                    )
                )
        for ev in events:
            entry = row.events_by_slug.get(ev.slug)
            cells.append(Td(score_cell(entry.points if entry else None), cls="num"))
        rows.append(Tr(*cells))

    if not rows:
        return Div("No riders in this category yet.", cls="empty")

    return Div(
        Div(Table(Thead(Tr(*headers)), Tbody(*rows)), cls="scrollx"),
        cls="card",
    )


def _fmt_total(value) -> str:
    v = float(value)
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def _fmt_points(value) -> str:
    v = float(value)
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def category_tabs(*, year: int, categories, active_code: str):
    return Div(
        *[
            A(
                cat.display_name,
                href=f"/{year}/{cat.code}",
                cls=f"category-tab{' active' if cat.code == active_code else ''}",
            )
            for cat in categories
        ],
        cls="category-tabs",
    )


def event_buttons(*, year: int, events, active_category_code: str, active_event_slug: str | None = None):
    """Row of race-name buttons shown above the class tabs. Each button
    links to that race's detail for the current category."""
    if not events:
        return Div()
    return Div(
        *[
            A(
                Span(f"{idx + 1:02d}", cls="event-btn-num"),
                Span(ev.name, cls="event-btn-name"),
                href=f"/{year}/{active_category_code}/{ev.slug}",
                cls=f"event-btn{' active' if ev.slug == active_event_slug else ''}",
            )
            for idx, ev in enumerate(events)
        ],
        cls="event-buttons",
    )
