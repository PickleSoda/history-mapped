"""Deterministic transcript lint for authors and reviewers.

Checks the rules a model tends to drift from at scale: facts numbered 1..N, an
explicit BCE/CE year on every fact (undated filler is the main padding symptom),
each fact's first year inside the era span, and chronological order. Year
extraction is a heuristic (the FIRST "<year> BCE|CE" or "<n>th century/millennium
BCE|CE" in the line), so era and order findings are warnings to verify, never
grounds to move a date.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline.agent.validate_handoff import ERA_BOUNDS
from pipeline.campaign.paths import FACT_NUM

# Era spans from the campaign spec; a boundary year belongs to the LATER era.
SPANS = {
    "e01": (-9000, -4001), "e02": (-4000, -1201), "e03": (-1200, -751), "e04": (-750, -331),
    "e05": (-330, -31), "e06": (-30, 499), "e07": (500, 999), "e08": (1000, 1349),
    "e09": (1350, 1749), "e10": (1750, 1999),
}
FACT_FLOOR, FACT_MAX = 60, 120
ORDER_TOLERANCE = 25  # years a fact may start before its predecessor without a warning

_NUM = r"(\d{1,3}(?:,\d{3})+|\d{1,5})"
YEAR = re.compile(rf"(?<![\d,]){_NUM}(?:\s*(?:–|—|-|to|and)\s*(?:c\.\s*)?{_NUM})?\s*(BCE|BC|CE|AD)\b")
PERIOD = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\s+(century|millennium)\s+(BCE|BC|CE|AD)\b", re.I)


def first_year(text: str) -> int | None:
    """Signed start year of the earliest explicit date in the text (BCE negative)."""
    hits = []
    m = YEAR.search(text)
    if m:
        n = int(m.group(1).replace(",", ""))
        hits.append((m.start(), -n if m.group(3) in ("BCE", "BC") else n))
    p = PERIOD.search(text)
    if p:
        n, unit, era = int(p.group(1)), p.group(2).lower(), p.group(3).upper()
        size = 1000 if unit == "millennium" else 100
        hits.append((p.start(), -n * size if era in ("BCE", "BC") else (n - 1) * size))
    return min(hits)[1] if hits else None


def _fmt(year: int) -> str:
    return f"{-year} BCE" if year < 0 else f"{year} CE"


@dataclass
class TranscriptReport:
    facts: int = 0
    dated: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)


def check_text(text: str, era: str | None) -> TranscriptReport:
    rep = TranscriptReport()
    facts: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = FACT_NUM.match(line)
        if m:
            facts.append((int(m.group(1)), line[m.end():].strip()))
    rep.facts = len(facts)
    if not facts:
        rep.errors.append(("no-facts", "no numbered fact lines ('1. ...')"))
        return rep

    numbers = [n for n, _ in facts]
    repeats = sorted({n for n in numbers if numbers.count(n) > 1})
    if repeats:
        rep.errors.append(("numbering", f"repeated fact numbers: {', '.join(map(str, repeats))}"))
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if gaps:
        rep.warnings.append(("numbering", f"missing fact numbers: {', '.join(map(str, gaps))} "
                             "(fine after extraction, where numbers are the handoff join key)"))
    if rep.facts < FACT_FLOOR:
        rep.warnings.append(("count", f"{rep.facts} facts < floor {FACT_FLOOR} (say why in notes.md if the topic is sparse)"))
    elif rep.facts > FACT_MAX:
        rep.warnings.append(("count", f"{rep.facts} facts > max {FACT_MAX}"))

    span, hard = SPANS.get(era or ""), ERA_BOUNDS.get(era or "")
    prev: tuple[int, int] | None = None
    for n, body in facts:
        year = first_year(body)
        if year is None:
            rep.errors.append(("undated", f"fact {n}: no explicit BCE/CE year: {body[:90]!r}"))
            continue
        rep.dated += 1
        if hard and not hard[0] <= year <= hard[1]:
            rep.warnings.append(("out-of-era", f"fact {n}: first year {_fmt(year)} is outside {era} "
                                 f"[{_fmt(hard[0])}, {_fmt(hard[1])}]: Spillover unless the year is misread"))
        elif span and not span[0] <= year <= span[1]:
            rep.warnings.append(("era-edge", f"fact {n}: first year {_fmt(year)} is outside the {era} span "
                                 f"{_fmt(span[0])}–{_fmt(span[1])}: keep only an era-defining straddler, else Spillover"))
        if prev and year < prev[1] - ORDER_TOLERANCE:
            rep.warnings.append(("order", f"fact {n} ({_fmt(year)}) starts before fact {prev[0]} ({_fmt(prev[1])})"))
        prev = (n, year)
    return rep
