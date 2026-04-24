"""Route handlers for the BGX dashboard (server-rendered via FastHTML)."""

from datetime import datetime

from fasthtml.common import (
    A,
    Div,
    H1,
    P,
    RedirectResponse,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)
from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from .config import DEFAULT_SEASON_YEAR
from .database import track_visit
from .db import get_session
from .db.models import Category, Event, EventResult, Rider, Season, Visit
from .services.rider import get_rider_profile, riders_sharing_number
from .services.standings import events_for_season, get_standings
from .ui.common import empty_state, fmt_ms, position_badge, points_pill
from .ui.event_detail import event_detail_table
from .ui.events_page import events_list
from .ui.layout import page
from .ui.rider_detail import rider_disambiguation, rider_header, rider_results_table
from .ui.standings import category_tabs, event_buttons, standings_table


def setup_routes(app, rt):
    @rt("/health")
    def health():
        from .config import APP_VERSION
        return {
            "status": "healthy",
            "service": "bgx-navigation-dashboard",
            "version": APP_VERSION,
        }

    @rt("/")
    def root():
        with get_session() as session:
            year = _pick_landing_year(session)
        return RedirectResponse(f"/{year}/", status_code=302)

    @rt("/{year:int}/")
    def season_landing(year: int):
        return _standings_page(year, category_code=None, request_user_agent_fn=None)

    @rt("/{year:int}/events")
    def events_page(year: int):
        with get_session() as session:
            season = _get_season(session, year)
            if season is None:
                return _not_found(year)
            all_years = _all_years(session)
            events = events_for_season(session, season)

        return page(
            title=f"Events · {year} · BGX",
            year=year,
            active_year=year,
            all_years=all_years,
            current_nav="events",
            body_children=[
                Div(
                    H1(f"{year} Events"),
                    P("The full season calendar."),
                    cls="page-header",
                ),
                events_list(year=year, events=events),
            ],
        )

    @rt("/{year:int}/events/{event_slug}")
    def event_overview(year: int, event_slug: str):
        with get_session() as session:
            season = _get_season(session, year)
            if season is None:
                return _not_found(year)
            all_years = _all_years(session)
            event = session.execute(
                select(Event).where(Event.season_id == season.id, Event.slug == event_slug)
            ).scalar_one_or_none()
            if event is None:
                return _not_found(year)
            categories = _categories(session, season)

        return page(
            title=f"{event.name} · {year} · BGX",
            year=year,
            active_year=year,
            all_years=all_years,
            current_nav="events",
            body_children=[
                Div(
                    H1(event.name),
                    P(
                        _format_event_subtitle(event),
                        cls="",
                    ),
                    cls="page-header",
                ),
                Div(
                    *[
                        A(
                            f"{cat.display_name}",
                            href=f"/{year}/{cat.code}/{event_slug}",
                            cls="category-tab",
                        )
                        for cat in categories
                    ],
                    cls="category-tabs",
                ),
                Div(
                    "Pick a category to see the full results for this event.",
                    cls="empty",
                ),
            ],
        )

    @rt("/{year:int}/r/{race_number:int}")
    def rider_by_number(year: int, race_number: int, request):
        with get_session() as session:
            season = _get_season(session, year)
            if season is None:
                return _not_found(year)
            all_years = _all_years(session)
            candidates = riders_sharing_number(session, season, race_number)

            if not candidates:
                return _not_found(year)
            if len(candidates) == 1:
                first, last = candidates[0]
                return _render_rider_detail(
                    session, year, season, race_number, first, last, all_years
                )

            return page(
                title=f"#{race_number} · {year} · BGX",
                year=year,
                active_year=year,
                all_years=all_years,
                current_nav="standings",
                body_children=[
                    rider_disambiguation(
                        year=year, race_number=race_number, riders=candidates
                    ),
                ],
            )

    @rt("/{year:int}/r/{race_number:int}/{slug}")
    def rider_by_number_and_slug(year: int, race_number: int, slug: str, request):
        with get_session() as session:
            season = _get_season(session, year)
            if season is None:
                return _not_found(year)
            all_years = _all_years(session)
            candidates = riders_sharing_number(session, season, race_number)

            match = next(
                (
                    (f, l)
                    for (f, l) in candidates
                    if _rider_slug(f, l) == slug.lower()
                ),
                None,
            )
            if match is None:
                return _not_found(year)
            first, last = match
            return _render_rider_detail(
                session, year, season, race_number, first, last, all_years
            )

    @rt("/{year:int}/{category_code}")
    def standings_view(year: int, category_code: str, request):
        user_agent = request.headers.get("user-agent", "")
        track_visit("standings", category_code, user_agent, season_year=year)
        return _standings_page(year, category_code=category_code, request_user_agent_fn=None)

    @rt("/{year:int}/{category_code}/{event_slug}")
    def event_detail(year: int, category_code: str, event_slug: str, request):
        user_agent = request.headers.get("user-agent", "")
        track_visit("event", category_code, user_agent, season_year=year)

        with get_session() as session:
            season = _get_season(session, year)
            if season is None:
                return _not_found(year)
            all_years = _all_years(session)
            category = session.execute(
                select(Category).where(
                    Category.season_id == season.id, Category.code == category_code
                )
            ).scalar_one_or_none()
            event = session.execute(
                select(Event).where(Event.season_id == season.id, Event.slug == event_slug)
            ).scalar_one_or_none()
            if category is None or event is None:
                return _not_found(year)

            categories = _categories(session, season)
            events = events_for_season(session, season)
            results = list(
                session.execute(
                    select(EventResult, Rider)
                    .join(Rider, Rider.id == EventResult.rider_id)
                    .where(
                        EventResult.event_id == event.id,
                        Rider.category_id == category.id,
                    )
                    .order_by(
                        EventResult.position.is_(None),
                        EventResult.position.asc(),
                        desc(EventResult.points),
                        Rider.race_number.asc(),
                    )
                )
            )
            has_timing = any(er.time_ms is not None for er, _ in results)

        return page(
            title=f"{event.name} · {category.display_name} · {year} · BGX",
            year=year,
            active_year=year,
            all_years=all_years,
            current_nav="events",
            body_children=[
                Div(
                    H1(f"{event.name} — {category.display_name}"),
                    P(_format_event_subtitle(event)),
                    cls="page-header",
                ),
                event_buttons(
                    year=year,
                    events=events,
                    active_category_code=category.code,
                    active_event_slug=event.slug,
                ),
                category_tabs(year=year, categories=categories, active_code=category.code),
                event_detail_table(results, has_timing=has_timing, year=year),
                Div(
                    A(f"← {year} {category.display_name} standings", href=f"/{year}/{category.code}"),
                    cls="page-header",
                    style="margin-top: 24px;",
                ),
            ],
        )

    @rt("/stats")
    def stats(request):
        user_agent = request.headers.get("user-agent", "")
        track_visit("stats", "", user_agent)

        with get_session() as session:
            all_years = _all_years(session)
            total = session.execute(select(func.count(Visit.id))).scalar_one()
            devices = dict(
                session.execute(
                    select(Visit.device_type, func.count(Visit.id)).group_by(Visit.device_type)
                ).all()
            )
            recent = list(
                session.execute(
                    select(Visit).order_by(Visit.timestamp.desc()).limit(25)
                ).scalars()
            )
            per_category = list(
                session.execute(
                    select(Visit.category, Visit.season_year, func.count(Visit.id))
                    .where(Visit.page == "standings")
                    .where(Visit.category.is_not(None))
                    .group_by(Visit.category, Visit.season_year)
                    .order_by(func.count(Visit.id).desc())
                ).all()
            )

        default_year = all_years[0] if all_years else DEFAULT_SEASON_YEAR
        stat_cards = Div(
            _stat("Total visits", total),
            _stat("Mobile", devices.get("mobile", 0)),
            _stat("Desktop", devices.get("desktop", 0)),
            _stat("Unknown", devices.get("unknown", 0)),
            cls="stat-grid",
        )

        cat_rows = [
            Tr(
                Td(cat or "—"),
                Td(str(year or "—"), cls="center mono"),
                Td(str(count), cls="num mono"),
            )
            for (cat, year, count) in per_category
        ]
        recent_rows = [
            Tr(
                Td(
                    Span(
                        v.timestamp.strftime("%Y-%m-%d %H:%M"),
                        cls="mono",
                    )
                ),
                Td(v.page or "—"),
                Td((v.category or "—")),
                Td(str(v.season_year or "—"), cls="center mono"),
                Td(v.device_type, cls="center"),
            )
            for v in recent
        ]

        return page(
            title="Visit stats · BGX",
            year=default_year,
            active_year=default_year,
            all_years=all_years,
            current_nav="stats",
            body_children=[
                Div(H1("Visit statistics"), P("Private analytics for this dashboard."), cls="page-header"),
                stat_cards,
                Div(
                    Div(Div("Categories", cls="page-header"), cls="card-header"),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Category"),
                                    Th("Season", cls="center"),
                                    Th("Visits", cls="num"),
                                )
                            ),
                            Tbody(*cat_rows) if cat_rows else Tbody(Tr(Td("No visits yet", colspan="3", cls="center"))),
                        ),
                        cls="scrollx",
                    ),
                    cls="card",
                ),
                Div(style="height: 24px;"),
                Div(
                    Div(Div("Recent activity", cls="page-header"), cls="card-header"),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("When"),
                                    Th("Page"),
                                    Th("Category"),
                                    Th("Season", cls="center"),
                                    Th("Device", cls="center"),
                                )
                            ),
                            Tbody(*recent_rows) if recent_rows else Tbody(Tr(Td("No visits yet", colspan="5", cls="center"))),
                        ),
                        cls="scrollx",
                    ),
                    cls="card",
                ),
            ],
        )


def _pick_landing_year(session) -> int:
    current = session.execute(
        select(Season.year).where(Season.is_current.is_(True)).order_by(Season.year.desc())
    ).scalar_one_or_none()
    if current:
        return current
    latest = session.execute(
        select(Season.year).order_by(Season.year.desc())
    ).scalar_one_or_none()
    return latest or DEFAULT_SEASON_YEAR


def _get_season(session, year: int):
    return session.execute(select(Season).where(Season.year == year)).scalar_one_or_none()


def _all_years(session) -> list[int]:
    return list(
        session.execute(select(Season.year).order_by(Season.year.desc())).scalars()
    )


def _categories(session, season: Season):
    return list(
        session.execute(
            select(Category)
            .where(Category.season_id == season.id)
            .order_by(Category.sort_order, Category.id)
        ).scalars()
    )


def _standings_page(year: int, *, category_code: str | None, request_user_agent_fn):
    with get_session() as session:
        season = _get_season(session, year)
        if season is None:
            return _not_found(year)
        all_years = _all_years(session)
        categories = _categories(session, season)
        if not categories:
            return page(
                title=f"{year} · BGX",
                year=year,
                active_year=year,
                all_years=all_years,
                current_nav="standings",
                body_children=[
                    Div(H1(f"{year} Season"), P(_season_subtitle(season, [])), cls="page-header"),
                    empty_state("No categories imported for this season yet."),
                ],
            )
        if category_code is None:
            return RedirectResponse(f"/{year}/{categories[0].code}", status_code=302)
        category = next((c for c in categories if c.code == category_code), None)
        if category is None:
            return RedirectResponse(f"/{year}/{categories[0].code}", status_code=302)

        events = events_for_season(session, season)
        standings_rows = get_standings(session, season, category)

    body_children = [
        Div(
            H1(f"{season.name}"),
            P(_season_subtitle(season, events)),
            cls="page-header",
        ),
        event_buttons(year=year, events=events, active_category_code=category.code),
        category_tabs(year=year, categories=categories, active_code=category.code),
        _standings_meta(category=category, events=events, rows=standings_rows),
        standings_table(
            year=year,
            category=category,
            events=events,
            standings_rows=standings_rows,
            championship_format=season.championship_format,
        ),
    ]

    return page(
        title=f"{category.display_name} · {year} · BGX",
        year=year,
        active_year=year,
        all_years=all_years,
        current_nav="standings",
        body_children=body_children,
    )


def _standings_meta(*, category, events, rows):
    total_riders = len(rows)
    total_events = len(events)
    leader = rows[0] if rows else None

    cards = [
        _stat("Category", category.display_name),
        _stat("Riders", total_riders),
        _stat("Events", total_events),
    ]
    if leader is not None:
        cards.append(
            _stat(
                "Leader",
                f"#{leader.rider.race_number} {leader.rider.first_name} {leader.rider.last_name}".strip(),
                secondary=f"{_fmt(leader.total_points)} pts",
            )
        )

    return Div(*cards, cls="stat-grid")


def _stat(label: str, value, *, secondary: str | None = None):
    children = [
        Div(label, cls="label"),
        Div(str(value), cls="value"),
    ]
    if secondary:
        children.append(Div(secondary, cls="rider-meta"))
    return Div(*children, cls="stat")


def _season_subtitle(season: Season, events) -> str:
    bits = []
    if events:
        bits.append(f"{len(events)} event{'s' if len(events) != 1 else ''}")
    if season.championship_format == "aggregate_2025":
        bits.append("drop-worst scoring (season total minus lowest race)")
    elif season.championship_format == "per_event":
        bits.append("per-event scoring, season total = sum of rounds")
    return " · ".join(bits) or "BGX Hard Enduro Championship"


def _format_event_subtitle(event) -> str:
    parts = []
    if event.event_date:
        parts.append(event.event_date.strftime("%B %-d, %Y"))
    if event.location:
        parts.append(event.location)
    if event.event_type:
        parts.append(event.event_type.title())
    return " · ".join(parts)


def _fmt(v) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


def _render_rider_detail(session, year, season, race_number, first, last, all_years):
    profile = get_rider_profile(session, season, race_number, first, last)
    if profile is None:
        return _not_found(year)
    has_timing = any(r.time_ms is not None for r in profile.results)
    return page(
        title=f"#{race_number} {first} {last} · {year} · BGX",
        year=year,
        active_year=year,
        all_years=all_years,
        current_nav="standings",
        body_children=[
            rider_header(profile=profile, year=year, has_timing=has_timing),
            rider_results_table(year=year, profile=profile, has_timing=has_timing),
        ],
    )


def _rider_slug(first: str, last: str) -> str:
    return f"{first.strip()}-{last.strip()}".replace(" ", "-").lower()


def _not_found(year: int):
    return page(
        title=f"Not found · BGX",
        year=year,
        active_year=year,
        all_years=[year],
        current_nav="standings",
        body_children=[
            Div(H1("Not found"), P("That page doesn't exist."), cls="page-header"),
        ],
    )
