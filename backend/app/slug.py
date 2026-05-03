"""Rider slug — disambiguates riders by (race_number, first_name, last_name).

The slug includes the rider's race_number on purpose: real-world rider names
collide. The 2024–2026 dataset has a "Иван ИВАНОВ" with four distinct race
numbers across categories — likely 2–4 different people the dashboard had no
way to disambiguate previously. Including the number guarantees each Rider
row gets its own URL.

Trade-off: a rider whose race_number CHANGES between seasons fragments into
separate /rider/{slug} URLs, one per number. The dashboard has no person_id,
so we can't link them; we'd rather show two accurate profiles than one
profile that secretly mixes two people.

Format: ``{first}-{last}-{race_number}``, lowercased, spaces → hyphens.
"""


def rider_slug(first: str, last: str, race_number: int) -> str:
    """Produce the canonical URL slug for a Rider row.

    Always include race_number — same name + different number means
    different identity (per the dataset's lack of person_id).
    """
    name_part = f"{first.strip()}-{last.strip()}".replace(" ", "-").lower()
    return f"{name_part}-{race_number}"
