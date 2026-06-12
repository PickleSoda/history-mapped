"""Normalize historical date strings to a signed-year-first form.

The database derives ``start_year``/``end_year`` from the date text with the
regex ``^-?\\d+`` (see the relationships/temporal-range triggers). That regex
does NOT understand "BCE": "2112 BCE" becomes +2112, so a BCE period whose start
is the larger number (2112 BCE → 2095 BCE) ends up with start_year > end_year
and trips the ``valid_year_range`` check constraint — and every BCE entity lands
in the wrong era (334 BCE rendered as 334 CE).

``normalize_historical_date`` converts "<n> BCE"/"<n> BC" to "-<n>" and strips a
leading wikidata-style "+", leaving everything else (already-signed ISO times,
plain CE years, full dates) untouched so the trigger parses the correct year.
"""
from __future__ import annotations

import re

_BCE_RE = re.compile(r"(\d{1,6})\s*(?:bce|bc)\b", re.IGNORECASE)


def normalize_historical_date(value: str | None) -> str | None:
    """Return a date string whose leading ``-?\\d+`` is the correct signed year."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value

    match = _BCE_RE.search(s)
    if match:
        return f"-{int(match.group(1))}"

    # Wikidata positive times come as "+0334-01-01T..."; the trigger's regex
    # doesn't match a leading "+", so drop it.
    if s.startswith("+"):
        return s[1:]

    return s
