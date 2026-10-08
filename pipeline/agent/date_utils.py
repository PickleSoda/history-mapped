"""Normalize historical date strings to a signed-year-first form.

The database derives ``start_year``/``end_year`` from the date text with the
regex ``^-?\\d+`` (see the relationships/temporal-range triggers). That regex
does NOT understand "BCE": "2112 BCE" becomes +2112, so a BCE period whose start
is the larger number (2112 BCE → 2095 BCE) ends up with start_year > end_year
and trips the ``valid_year_range`` check constraint — and every BCE entity lands
in the wrong era (334 BCE rendered as 334 CE).

``normalize_historical_date`` converts "<n> BCE"/"<n> BC" to "-<n>", strips a
leading wikidata-style "+", strips the ISO time portion ("1945-04-30T00:00:00Z"
→ "1945-04-30"), and strips a trailing "CE"/"AD" marker ("1933 CE" → "1933") so
dates are stored in a clean, consistent, signed-year-first form (no raw
timestamps, no mixed "1933 CE"/"1945-04-30T..." pairs) and the trigger still
parses the correct year.
"""
from __future__ import annotations

import re

_BCE_RE = re.compile(r"(\d{1,6})\s*(?:bce|bc)\b", re.IGNORECASE)
_CE_SUFFIX_RE = re.compile(r"\s*(?:CE|AD)\.?$", re.IGNORECASE)


def normalize_historical_date(value: str | None) -> str | None:
    """Return a clean, signed-year-first date string (no ISO time, no CE/AD)."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value

    match = _BCE_RE.search(s)
    if match:
        return f"-{int(match.group(1))}"

    # Wikidata positive times come as "+0334-01-01T..."; drop the leading "+".
    if s.startswith("+"):
        s = s[1:]

    # Drop the ISO time portion: "1945-04-30T00:00:00Z" → "1945-04-30".
    if "T" in s:
        s = s.split("T", 1)[0]

    # Drop a trailing era marker: "1933 CE" → "1933".
    s = _CE_SUFFIX_RE.sub("", s).strip()

    return s


# ── Lifespan sanity ──────────────────────────────────────────────────────────
# A person's stored [start, end] is a lifespan. Over 110 years it is never real:
# it is a BCE/CE sign slip ("-1015".."1072" for Bagrat IV, born 1018 CE), a
# Wikidata namesake's birth glued to the transcript's death date, a century-
# precision Wikidata date stored as a year ("-0100".."0100" = "1st century BCE"
# .."1st century"), or a radiocarbon/floruit window given as birth and death.
# The same limit is enforced by `handoff check`, validate_handoff, the Wikidata
# date fill (resolve_wikidata), the campaign measure and ImportEntityJob
# (MAX_PERSON_LIFESPAN_YEARS there).
MAX_PERSON_LIFESPAN = 110


def lifespan_problem(entity_type: str | None, start_year: int | None,
                     end_year: int | None) -> str | None:
    """Why a dated span can't be stored as-is, or None when it is fine.

    Any type: start after end. Persons only: a span over MAX_PERSON_LIFESPAN
    years, described as a sign split when it crosses year 0 (one bound BCE, the
    other CE: the classic missing/extra minus).
    """
    if start_year is None or end_year is None:
        return None
    if start_year > end_year:
        return f"start {start_year} > end {end_year}"
    if entity_type == "person" and end_year - start_year > MAX_PERSON_LIFESPAN:
        span = end_year - start_year
        if start_year < 0 < end_year:
            return (f"sign split: lifespan {start_year}..{end_year} ({span} years) crosses year 0; "
                    "one bound is probably missing or carrying a minus")
        return f"lifespan {start_year}..{end_year} is {span} years (> {MAX_PERSON_LIFESPAN})"
    return None
