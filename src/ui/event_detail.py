"""Per-event detail view — shows rich timing data when available."""

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

from .common import fmt_ms, position_badge, points_pill


def _rider_link(year: int, rider) -> str:
    slug = f"{rider.first_name.strip()}-{rider.last_name.strip()}".replace(" ", "-").lower()
    return f"/{year}/r/{rider.race_number}/{slug}"


def event_detail_table(results: list, *, has_timing: bool, year: int = None):
    headers = [
        Th("#", cls="center"),
        Th("No.", cls="center"),
        Th("Rider"),
        Th("Points", cls="center"),
    ]
    if has_timing:
        headers += [
            Th("Total Time", cls="num"),
            Th("Gap", cls="num"),
            Th("GPS Pen.", cls="num"),
            Th("Laps", cls="center"),
        ]

    rows = []
    for er, rider in results:
        href = _rider_link(year, rider) if year is not None else None
        number_cell = (
            A(str(rider.race_number), href=href, cls="mono") if href else str(rider.race_number)
        )
        name_cell = (
            A(f"{rider.first_name} {rider.last_name}", href=href, cls="rider-name")
            if href
            else Div(f"{rider.first_name} {rider.last_name}", cls="rider-name")
        )
        cells = [
            Td(position_badge(er.position), cls="center"),
            Td(number_cell, cls="center"),
            Td(
                name_cell,
                Div(rider.team or "", cls="rider-meta") if rider.team else None,
            ),
            Td(points_pill(er.points), cls="center"),
        ]
        if has_timing:
            cells += [
                Td(Span(fmt_ms(er.time_ms, show_ms=True), cls="mono"), cls="num"),
                Td(
                    Span(fmt_ms(er.gap_ms, show_ms=True) if er.gap_ms else "—", cls="mono"),
                    cls="num",
                ),
                Td(
                    Span(fmt_ms(er.gps_penalty_ms) if er.gps_penalty_ms else "—", cls="mono"),
                    cls="num",
                ),
                Td(str(er.laps) if er.laps is not None else "—", cls="center"),
            ]
        rows.append(Tr(*cells))

    if not rows:
        return Div("No results for this event yet.", cls="empty")

    return Div(
        Div(Table(Thead(Tr(*headers)), Tbody(*rows)), cls="scrollx"),
        cls="card",
    )
