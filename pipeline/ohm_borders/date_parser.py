"""Parse OHM date strings into signed integer years, in our numbering.

OHM writes ISO 8601 dates, which number years astronomically: 0000 is 1 BCE
and -0043 is 44 BCE. Our years are historical, with no year 0 (-44 is 44 BCE).
"""

from __future__ import annotations

import re

_YEAR_RE = re.compile(r"^(-?\d+)")


def from_ohm_year(year: int) -> int:
    """Our year for an OHM (astronomical) year: 0 -> -1 (1 BCE), -43 -> -44."""
    return year - 1 if year <= 0 else year


def _extract_year(raw: str | None) -> int | None:
    if not raw:
        return None

    match = _YEAR_RE.match(raw.strip())
    if not match:
        return None

    return from_ohm_year(int(match.group(1)))


def parse_start_year(raw: str | None) -> int | None:
    """Extract start year from OHM date text."""
    return _extract_year(raw)


def parse_end_year(raw: str | None) -> int | None:
    """Extract end year from OHM date text."""
    return _extract_year(raw)
