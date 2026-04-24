"""Tiny presentational helpers shared across views."""

from fasthtml.common import Div, Span


def position_badge(position):
    if position is None:
        return Span("DNF", cls="pos pos-dnf")
    cls = "pos"
    if position == 1:
        cls = "pos pos-1"
    elif position == 2:
        cls = "pos pos-2"
    elif position == 3:
        cls = "pos pos-3"
    return Span(str(position), cls=cls)


def points_pill(points):
    if points is None or points == 0:
        return Span("—", cls="score-dim")
    p = float(points)
    cls = "points"
    if p >= 25:
        cls = "points points-25"
    return Span(_fmt_points(p), cls=cls)


def score_cell(points):
    """Small per-event score rendering inside a standings table."""
    if points is None:
        return Span("—", cls="score-dim")
    p = float(points)
    if p == 0:
        return Span("0", cls="score-dim")
    return Span(_fmt_points(p), cls="score")


def _fmt_points(p: float) -> str:
    if p == int(p):
        return str(int(p))
    return f"{p:g}"


def fmt_ms(ms, *, show_ms: bool = False) -> str:
    if ms is None:
        return "—"
    total_seconds = ms / 1000
    hours, rem = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(rem, 60)
    if show_ms:
        frac = ms - int(total_seconds) * 1000
        return f"{hours:d}:{minutes:02d}:{seconds:02d}.{frac // 100}"
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def empty_state(message: str):
    return Div(message, cls="empty")
