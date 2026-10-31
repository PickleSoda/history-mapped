"""Date tolerances and comparisons for the identity audit (C2c, C6, C7).

The plan's tolerances: people ±5 years, events ±2, polities ±25. A coarse
Wikidata value widens the tolerance by what its precision allows (decade 10,
century 100, millennium 1000), and before 1000 BCE chronologies disagree, so
another 25 years are allowed there.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.agent.tools.disambiguation import temporal_fit

PERSON_TOLERANCE = 5
EVENT_TOLERANCE = 2
POLITY_TOLERANCE = 25

EVENT_TYPES = {
    "event_war", "event_battle", "event_treaty", "event_rebellion", "event_natural_disaster",
    "event_tech_adoption", "event_legal_reform", "migration", "epidemic_disease",
}
POLITY_TYPES = {"political_entity", "dynasty", "military_unit", "diplomatic_relationship"}
# Types whose dates are an identity signal. Places, works and ideas carry fuzzy
# or open-ended spans (a city "founded" in prehistory, a book's century).
DATED_TYPES = {"person"} | EVENT_TYPES | POLITY_TYPES

PRECISION_SLACK = {6: 1000, 7: 100, 8: 10}
DEEP_ANTIQUITY = -1000
DEEP_ANTIQUITY_EXTRA = 25


def tolerance(entity_type: str | None) -> int | None:
    if entity_type == "person":
        return PERSON_TOLERANCE
    if entity_type in EVENT_TYPES:
        return EVENT_TOLERANCE
    if entity_type in POLITY_TYPES:
        return POLITY_TOLERANCE
    return None


def wd_bounds(entity_type: str, dates: dict[str, list[int]]) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    """((start_year, precision), (end_year, precision)) from a record's dates.

    People: birth P569 / death P570. Everything else: inception P571 or start
    time P580, else point in time P585 (or publication P577); dissolved P576
    or end time P582, else the same point."""
    def first(*props: str):
        for p in props:
            if p in dates:
                return tuple(dates[p])
        return None

    if entity_type == "person":
        return first("P569"), first("P570")
    if entity_type in EVENT_TYPES:
        start = first("P580", "P585", "P571", "P577")
        end = first("P582", "P585", "P576")
    else:
        start = first("P571", "P580", "P585", "P577")
        end = first("P576", "P582", "P585")
    if start and not end and "P585" in dates:
        end = start
    return start, end


def _off(row_year: int | None, wd: tuple[int, int] | None, tol: int) -> int | None:
    """Years beyond tolerance (0 = within, None = not comparable)."""
    if row_year is None or wd is None:
        return None
    year, precision = wd
    allow = tol + PRECISION_SLACK.get(precision, 0)
    if min(row_year, year) < DEEP_ANTIQUITY:
        allow += DEEP_ANTIQUITY_EXTRA
    return max(0, abs(row_year - year) - allow)


def compare_dates(entity_type: str, row_start: int | None, row_end: int | None,
                  dates: dict[str, list[int]]) -> dict[str, Any]:
    """Compare a row's span with its QID's dates.

    verdict: 'ok' | 'out_of_tolerance' | 'conflict' | 'sign' | 'unknown'.
    'conflict' = the spans are clearly different eras (temporal_fit 'conflict',
    the namesake guard's verdict); 'sign' = only the row's BCE/CE sign differs.
    """
    tol = tolerance(entity_type)
    start, end = wd_bounds(entity_type, dates)
    out: dict[str, Any] = {"wd_start": start[0] if start else None, "wd_end": end[0] if end else None,
                           "verdict": "unknown", "off": None}
    if tol is None:
        return out
    offs = [o for o in (_off(row_start, start, tol), _off(row_end, end, tol)) if o is not None]
    if not offs:
        return out
    worst = max(offs)
    out["off"] = worst
    if worst == 0:
        out["verdict"] = "ok"
        return out
    flipped = [o for o in (_off(-row_start if row_start is not None else None, start, tol),
                           _off(-row_end if row_end is not None else None, end, tol)) if o is not None]
    if flipped and max(flipped) == 0:
        out["verdict"] = "sign"
        return out
    wd_span = _span(start[0] if start else None, end[0] if end else None, start, end)
    row_span = _span(row_start, row_end)
    fit = temporal_fit(entity_type, row_span, wd_span) if row_span and wd_span else "unknown"
    gap = max(0, max(row_span[0], wd_span[0]) - min(row_span[1], wd_span[1])) if row_span and wd_span else 0
    out["gap"] = gap
    out["verdict"] = "conflict" if fit == "conflict" or gap > CONFLICT_GAP.get(entity_type, 10**9) \
        else "out_of_tolerance"
    return out


# Years by which two spans must miss each other to be different eras (not a
# loose date): two lifespans that do not overlap by more than a decade are two
# people; two battles a decade apart are two battles.
CONFLICT_GAP = {
    "person": 10, "event_battle": 10, "event_treaty": 10, "event_rebellion": 25, "event_war": 25,
    "event_natural_disaster": 10, "event_tech_adoption": 50, "event_legal_reform": 25, "migration": 50,
    "epidemic_disease": 50, "military_unit": 100, "dynasty": 100, "diplomatic_relationship": 50,
    "political_entity": 150,
}


def _span(a: int | None, b: int | None, pa=None, pb=None) -> tuple[int, int] | None:
    lo = a if a is not None else b
    hi = b if b is not None else a
    if lo is None or hi is None:
        return None
    lo, hi = min(lo, hi), max(lo, hi)
    # widen coarse Wikidata bounds by their precision
    if pa and pa[1] in PRECISION_SLACK:
        lo -= PRECISION_SLACK[pa[1]]
    if pb and pb[1] in PRECISION_SLACK:
        hi += PRECISION_SLACK[pb[1]]
    return lo, hi


OPEN = 10**5


def row_range(entity_type: str, start: int | None, end: int | None) -> tuple[int, int] | None:
    """A row's span for era comparisons, reading a missing bound as open.

    Events with one date are points. A person with one date lived within a
    century of it. Polities, dynasties, units and everything else with only a
    start (England 927) are ongoing from it, not points."""
    if start is None and end is None:
        return None
    if start is not None and end is not None:
        return (min(start, end), max(start, end))
    if entity_type in EVENT_TYPES:
        y = start if start is not None else end
        return (y, y)
    if entity_type == "person":
        return (start, start + 100) if start is not None else (end - 100, end)
    return (start, OPEN) if start is not None else (-OPEN, end)


# ── years named in text (C6, and the namesake text check) ───────────────────
_ERA_YEAR = re.compile(
    r"\b(?:(?:AD|A\.D\.)\s*(\d{1,4})\b|(\d{1,4}(?:,\d{3})?)\s*(BCE|BC|B\.C\.E?\.?|CE|AD|A\.D\.)(?![a-z]))")
_BARE_YEAR = re.compile(r"(?<![\d,.\-–])\b(1[0-9]{3}|20[0-2][0-9])\b(?![\d,]|\s*(?:km|kilomet|mile|metre|meter|men|soldiers|troops|ships|people))")
_CENTURY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)[\s-]+century\s*(BCE|BC)?", re.I)


def text_years(text: str) -> list[int]:
    """Signed years named in a text: '480 BCE' -> -480, 'AD 9' -> 9, '1066' -> 1066.

    Bare numbers count only as 1000-2029 (smaller ones are usually counts)."""
    years: list[int] = []
    if not text:
        return years
    taken: list[tuple[int, int]] = []
    for m in _ERA_YEAR.finditer(text):
        if m.group(1):
            years.append(int(m.group(1)))
        else:
            n = int(m.group(2).replace(",", ""))
            era = m.group(3).upper().replace(".", "")
            years.append(-n if era.startswith("B") else n)
        taken.append(m.span())
    for m in _BARE_YEAR.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        # a bare year directly after a BCE year in a range ('490–480 BCE') is BCE
        tail = text[m.end():m.end() + 12]
        if re.match(r"\s*[–-]\s*\d{1,4}\s*(BCE|BC)", tail):
            years.append(-int(m.group(1)))
        else:
            years.append(int(m.group(1)))
    return years


def years_fit(years: list[int], span: tuple[int, int] | None, tol: int) -> list[bool]:
    if span is None:
        return []
    lo, hi = span
    return [lo - tol <= y <= hi + tol for y in years]
