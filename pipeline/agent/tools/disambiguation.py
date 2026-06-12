"""Era-aware Wikidata disambiguation helpers.

The label/keyword ranking in ``_rank_candidates`` is era-blind: "Philip II of
Macedon" and "Philip II of Spain" score the same for the search term "Philip
II", so the wrong one (Spain, 1527-1598) gets picked for a 4th-century-BCE
context. These helpers add a temporal signal: compute the entity's era (its own
date, else the transcript's median event year) and re-rank candidates by how
close their Wikidata dates are to it.

The pure scoring (``rerank_by_era``) is separated from the network fetch so it
can be unit-tested without hitting Wikidata.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Any

from pipeline.agent.date_utils import normalize_historical_date

_LEADING_YEAR_RE = re.compile(r"^(-?\d{1,6})")


def era_year(date_str: Any) -> int | None:
    """Parse a signed year from a date string ('334 BCE' -> -334, '1453' -> 1453)."""
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    norm = normalize_historical_date(date_str) or ""
    match = _LEADING_YEAR_RE.match(norm.strip())
    return int(match.group(1)) if match else None


def context_era(events: list[Any]) -> int | None:
    """Median year across the parsed events — the transcript's temporal centre.

    Used as a fallback era for entities the extractor didn't date.
    """
    years: list[int] = []
    for event in events:
        for date in (getattr(event, "start_date", None), getattr(event, "end_date", None)):
            year = era_year(date)
            if year is not None:
                years.append(year)
    if not years:
        return None
    return int(median(sorted(years)))


def rerank_by_era(
    candidates: list[dict[str, Any]],
    target_era: int | None,
    dates_by_qid: dict[str, dict[str, Any]],
    *,
    close: int = 150,
    far: int = 400,
    bonus: float = 0.3,
    penalty: float = 0.4,
) -> list[dict[str, Any]]:
    """Adjust candidate scores by temporal proximity, then re-sort.

    ``dates_by_qid`` maps qid -> {'start_date': ..., 'end_date': ...} (already
    fetched). A candidate within ``close`` years of ``target_era`` gets +``bonus``;
    one more than ``far`` years away gets -``penalty``. Candidates with no usable
    date are left untouched. Mutates ``score`` and annotates ``era_year``/``era_diff``.
    """
    if target_era is None:
        return candidates

    for cand in candidates:
        info = dates_by_qid.get(cand.get("qid"), {})
        cand_era = era_year(info.get("start_date"))
        if cand_era is None:
            cand_era = era_year(info.get("end_date"))
        if cand_era is None:
            continue
        diff = abs(target_era - cand_era)
        cand["era_year"] = cand_era
        cand["era_diff"] = diff
        score = cand.get("score", 0.0)
        if diff <= close:
            cand["score"] = round(min(1.0, score + bonus), 3)
        elif diff >= far:
            cand["score"] = round(max(0.0, score - penalty), 3)

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates


def is_ambiguous(candidates: list[dict[str, Any]], gap: float = 0.25) -> bool:
    """True when the top two candidates are within ``gap`` — worth era-disambiguating."""
    if len(candidates) < 2:
        return False
    return (candidates[0].get("score", 0.0) - candidates[1].get("score", 0.0)) < gap
