"""Padded ``-01-01`` dates: detect them and give the date the fact actually supports.

Extraction agents sometimes write a year-only fact ("In 1873 CE ...") as
``"1873-01-01"``. Nothing downstream can tell that apart from a real 1 January:
the commit writer and the Laravel importer store the string verbatim
(``entity_temporal_ranges.start_date``, ``relationships.temporal_start``), so the
atlas shows false day precision. A ``-01-01`` date is kept only when a transcript
fact states 1 January of that year: the item's own fact, or (as a fallback) any
fact of the same transcript that names "1 January <year>" explicitly, which covers
an entity or relation whose bound is dated by a neighbouring fact (e.g. the
Haitian Revolution ending on 1 January 1804).

Wikidata-sourced dates never reach this path padded: ``tools.wikidata._wikidata_date``
already drops year-precision values to year-only.
"""
from __future__ import annotations

import re
from typing import Iterable

JAN1_DATE = re.compile(r"^(-?\d+)-01-01$")
_DAY1 = r"(?:1st|first|1)"
_JAN = r"jan(?:uary)?\.?(?!\w)"
_YEAR_AFTER = r"(?:\s*,?\s*(\d{1,5})(?!\d))?"
# "1 January [1801]", "1st of January", "January 1[, 1801]", "New Year's Day [1801]".
_JAN1_PHRASES = [
    re.compile(rf"(?<![\d\w]){_DAY1}\s+(?:of\s+)?{_JAN}{_YEAR_AFTER}", re.IGNORECASE),
    re.compile(rf"\b{_JAN}\s+{_DAY1}(?![\d\w]){_YEAR_AFTER}", re.IGNORECASE),
    re.compile(rf"\bnew\s+year['’]?s\s+day{_YEAR_AFTER}", re.IGNORECASE),
]
# "January [1873]" with no day, or with a day other than 1 ("11 January" is still January).
_JANUARY = re.compile(rf"\b{_JAN}(?:\s+\d{{1,2}}(?:st|nd|rd|th)?(?!\d))?{_YEAR_AFTER}", re.IGNORECASE)


def _year_in(text: str, year: int) -> bool:
    return re.search(rf"(?<!\d){abs(year)}(?!\d)", text) is not None


def _mentions(patterns: Iterable[re.Pattern], text: str, year: int) -> bool:
    """True when a pattern matches with an explicit year equal to |year|, or with no
    explicit year while the year appears elsewhere in the text."""
    for pat in patterns:
        for m in pat.finditer(text):
            stated = m.group(1)
            if stated is not None:
                if int(stated) == abs(year):
                    return True
            elif _year_in(text, year):
                return True
    return False


def states_jan1(text: str | None, year: int) -> bool:
    """Does `text` state 1 January of `year`?"""
    return bool(text) and _mentions(_JAN1_PHRASES, text, year)


def jan1_years(texts: Iterable[str]) -> set[int]:
    """Years a transcript states "1 January <year>" for explicitly (fallback evidence)."""
    years: set[int] = set()
    for text in texts:
        for pat in _JAN1_PHRASES:
            years.update(int(m.group(1)) for m in pat.finditer(text or "") if m.group(1))
    return years


def is_jan1(date: object) -> bool:
    return isinstance(date, str) and JAN1_DATE.match(date.strip()) is not None


def depad(date: object, fact_text: str | None = None,
          transcript_jan1: Iterable[int] = ()) -> str | None:
    """Corrected value for a padded ``YYYY-01-01``, or None when `date` is fine.

    Fine = not a ``-01-01`` date, or 1 January of that year is stated by the fact
    (or explicitly by another fact of the transcript). Otherwise the fix is
    ``YYYY-01`` when the fact names January of that year, else the bare year.
    """
    if not is_jan1(date):
        return None
    year = int(JAN1_DATE.match(date.strip()).group(1))
    text = fact_text or ""
    if states_jan1(text, year) or abs(year) in set(transcript_jan1):
        return None
    if _mentions([_JANUARY], text, year):
        return f"{year}-01"
    return str(year)
