"""Season event schedule / list page."""

from fasthtml.common import A, Div, Span, Table, Tbody, Td, Th, Thead, Tr


def events_list(*, year: int, events: list, event_types=None):
    if not events:
        return Div("No events scheduled for this season yet.", cls="empty")

    rows = []
    for ev in events:
        rows.append(
            Tr(
                Td(str(ev.sort_order + 1), cls="center mono"),
                Td(
                    A(ev.name, href=f"/{year}/events/{ev.slug}", cls="rider-name"),
                    Div(ev.location or "", cls="rider-meta") if ev.location else None,
                ),
                Td(ev.event_date.isoformat() if ev.event_date else "TBD", cls="mono"),
                Td(
                    Span((ev.event_type or "").upper(), cls="badge") if ev.event_type else "",
                    cls="center",
                ),
            )
        )

    return Div(
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Rd.", cls="center"),
                        Th("Event"),
                        Th("Date"),
                        Th("Type", cls="center"),
                    )
                ),
                Tbody(*rows),
            ),
            cls="scrollx",
        ),
        cls="card",
    )
