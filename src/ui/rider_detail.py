"""Rider detail — one person's results across all their categories."""

from fasthtml.common import (
    A,
    Div,
    H1,
    P,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)

from .common import fmt_ms, points_pill, position_badge


def rider_header(*, profile, year: int, has_timing: bool):
    cat_labels = " · ".join(c.display_name for c in profile.categories)
    meta_bits = []
    if profile.team:
        meta_bits.append(profile.team)
    if profile.bike:
        meta_bits.append(profile.bike)

    return Div(
        Div(
            Span(f"#{profile.race_number}", cls="mono"),
            Span(" "),
            Span(f"{profile.first_name} {profile.last_name}"),
            cls="",
            style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em;",
        ),
        P(" · ".join(meta_bits) if meta_bits else "", cls="rider-meta"),
        Div(
            *[
                A(c.display_name, href=f"/{year}/{c.code}", cls="badge badge-accent")
                for c in profile.categories
            ],
            style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;",
        ),
        cls="page-header",
    )


def rider_results_table(*, year: int, profile, has_timing: bool):
    if not profile.results:
        return Div("No results recorded for this rider.", cls="empty")

    headers = [
        Th("Event"),
        Th("Class", cls="center"),
        Th("Pos", cls="center"),
        Th("Points", cls="center"),
    ]
    if has_timing:
        headers += [
            Th("Time", cls="num"),
            Th("Gap", cls="num"),
            Th("GPS Pen.", cls="num"),
        ]

    rows = []
    for r in profile.results:
        cells = [
            Td(
                A(
                    r.event.name,
                    href=f"/{year}/{r.category.code}/{r.event.slug}",
                    cls="rider-name",
                ),
                Div(
                    r.event.event_date.isoformat() if r.event.event_date else "",
                    cls="rider-meta",
                ),
            ),
            Td(
                A(
                    r.category.display_name,
                    href=f"/{year}/{r.category.code}",
                    cls="badge",
                ),
                cls="center",
            ),
            Td(position_badge(r.position), cls="center"),
            Td(points_pill(r.points), cls="center"),
        ]
        if has_timing:
            cells += [
                Td(Span(fmt_ms(r.time_ms, show_ms=True) if r.time_ms else "—", cls="mono"), cls="num"),
                Td(Span(fmt_ms(r.gap_ms, show_ms=True) if r.gap_ms else "—", cls="mono"), cls="num"),
                Td(Span(fmt_ms(r.gps_penalty_ms) if r.gps_penalty_ms else "—", cls="mono"), cls="num"),
            ]
        rows.append(Tr(*cells))

    return Div(
        Div(Table(Thead(Tr(*headers)), Tbody(*rows)), cls="scrollx"),
        cls="card",
    )


def rider_disambiguation(*, year: int, race_number: int, riders: list[tuple[str, str]]):
    """Shown when a single race_number maps to multiple people in one season."""
    return Div(
        H1(f"#{race_number} — multiple riders"),
        P("Two riders share this race number in this season. Pick one:"),
        Div(
            *[
                A(
                    f"{first} {last}",
                    href=f"/{year}/r/{race_number}/{_slug(first, last)}",
                    cls="category-tab",
                )
                for first, last in riders
            ],
            cls="category-tabs",
        ),
        cls="page-header",
    )


def _slug(first: str, last: str) -> str:
    # URL-safe-ish: keep Unicode, replace whitespace with dashes. Starlette
    # percent-encodes Cyrillic automatically. The slug only needs to be stable
    # enough to distinguish two people sharing one race number.
    return f"{first.strip()}-{last.strip()}".replace(" ", "-").lower()
