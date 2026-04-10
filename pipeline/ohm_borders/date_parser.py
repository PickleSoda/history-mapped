"""Parse OHM date strings into signed integer years."""

from __future__ import annotations

import re

_YEAR_RE = re.compile(r"^(-?\d+)")


def _extract_year(raw: str | None) -> int | None:
    if not raw:
        return None

    match = _YEAR_RE.match(raw.strip())
    if not match:
        return None

    return int(match.group(1))


def parse_start_year(raw: str | None) -> int | None:
    """Extract start year from OHM date text."""
    return _extract_year(raw)


def parse_end_year(raw: str | None) -> int | None:
    """Extract end year from OHM date text."""
    return _extract_year(raw)
