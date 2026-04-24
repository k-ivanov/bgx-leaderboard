"""Rider slug — pinned to the exact algorithm used by the legacy FastHTML app.

A rider is identified within a season by the tuple (race_number, first, last).
URLs of the form `/{year}/r/{race_number}/{slug}` have been public since launch,
so the slug must remain byte-identical to avoid link rot.

See eng-review.md CQ-1 / N4: any future switch to a richer slugifier requires
a redirect table. Do not alter this function without that plan in place.
"""


def rider_slug(first: str, last: str) -> str:
    """Produce the canonical URL slug for a rider.

    Identical to ``backend/src/routes.py::_rider_slug`` as of commit cab66a3.
    """
    return f"{first.strip()}-{last.strip()}".replace(" ", "-").lower()
