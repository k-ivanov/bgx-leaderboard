"""Base page layout, navigation, year switcher, footer."""

from fasthtml.common import (
    A,
    Body,
    Div,
    Footer,
    Head,
    Html,
    Meta,
    Nav,
    P,
    Span,
    Title,
)

from ..config import APP_VERSION
from .styles import base_styles


def page(*, title: str, year: int, active_year: int, all_years: list[int], current_nav: str = "standings", body_children=()):
    return Html(
        Head(
            Title(title),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            base_styles(),
        ),
        Body(
            _nav(active_year=active_year, all_years=all_years, current_nav=current_nav),
            Div(*body_children, cls="container"),
            _footer(),
        ),
    )


def _nav(*, active_year: int, all_years: list[int], current_nav: str):
    year_links = [
        A(
            str(y),
            href=f"/{y}/",
            cls=("active" if y == active_year else ""),
        )
        for y in sorted(all_years, reverse=True)
    ]
    nav_link = lambda href, label, key: A(
        label,
        href=href,
        cls=("active" if current_nav == key else ""),
    )
    return Nav(
        Div(
            Div(
                Span("BGX"),
                Span(".", cls="dot"),
                Span("Hard Enduro"),
                cls="brand",
            ),
            Div(*year_links, cls="year-switcher") if all_years else Div(),
            Div(
                nav_link(f"/{active_year}/", "Standings", "standings"),
                nav_link(f"/{active_year}/events", "Events", "events"),
                cls="nav-links",
            ),
            cls="nav-inner",
        ),
        cls="nav",
    )


def _footer():
    return Footer(
        P(f"BGX Hard Enduro Championship · Unofficial · v{APP_VERSION}"),
        cls="footer",
    )
