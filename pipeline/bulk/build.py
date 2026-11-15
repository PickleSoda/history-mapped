"""Raw Wikidata items -> import records, with each slice's quality gates."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from pipeline.bulk.fetch import start_precision
from pipeline.bulk.spec import Slice
from pipeline.wikidata.mapper.entity_mapper import EntityMapper

# Bulk rows rank by notability but below the hand-curated median (70)
# unless widely covered: 3 sitelinks -> 45, 10 -> 56, 30 -> 66, 100 -> 76.
IMPACT_MIN, IMPACT_MAX = 30, 80
CURRENT_YEAR = 2026
# Hints bulk rows never stage:
# - P17 (country) and P131 (admin territory) name today's units: a hint
#   would make the Battle of Zela "part of Turkey". They still give the row
#   its location name.
# - P39 (position held) names an office, not a realm: it resolved to rows
#   like Daimyo or Constable of France as "rules".
DROPPED_HINTS = {"wikidata:P17", "wikidata:P131", "wikidata:P39"}


# A lead that is really a hatnote or a disambiguation line says nothing about
# the row; the mapper then falls back to the Wikidata description.
HATNOTE = re.compile(r"(may (also )?refer to|^see also\b|^for other uses\b|^this article is about\b)", re.I)


def impact_from_sitelinks(sitelinks: int) -> int:
    if sitelinks <= 0:
        return IMPACT_MIN
    return max(IMPACT_MIN, min(IMPACT_MAX, round(35 + 9 * math.log(sitelinks))))


def _year(v: Any) -> int | None:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


def _in_box(record: dict[str, Any], box: list[float] | None) -> bool:
    coords = (record.get("geojson") or {}).get("coordinates")
    if not box or not coords:
        return False
    lon, lat = coords[0], coords[1]
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def gate(raw: dict[str, Any], record: dict[str, Any], s: Slice) -> str | None:
    """Why this row is dropped, or None to keep it."""
    if not record.get("name") or record["name"] == raw.get("qid"):
        return "no-label"
    if set(raw.get("p31") or []) & set(s.exclude_p31):
        return "excluded-class"
    start, end = _year(record.get("temporal_start")), _year(record.get("temporal_end"))
    if start is None and end is None:
        if "dates" in s.require:
            return "no-dates"
        if set(raw.get("p31") or []) & set(s.require_dates_p31) and not _in_box(record, s.require_dates_except_bbox):
            return "no-dates"
    if "coords" in s.require and not record.get("geojson"):
        return "no-coords"
    if start is not None and end is not None and end < start:
        return "end-before-start"
    for y in (start, end):
        if y is not None and (y > CURRENT_YEAR or y == 0):
            return "impossible-year"
    first = start if start is not None else end
    if first is not None:
        if s.year_min is not None and first < s.year_min:
            return "before-year-min"
        if s.year_max is not None and first > s.year_max:
            return "after-year-max"
    return None


def build(raws: list[dict[str, Any]], s: Slice, mapper: EntityMapper | None = None) -> tuple[list[dict], Counter]:
    mapper = mapper or EntityMapper()
    kept: list[dict] = []
    dropped: Counter = Counter()
    for raw in raws:
        if HATNOTE.search(raw.get("summary") or ""):
            raw = {k: v for k, v in raw.items() if k not in ("summary", "full_extract")}
        record = mapper.map(raw, s.entity_type)
        if record is None:
            dropped["unmappable"] += 1
            continue
        reason = gate(raw, record, s)
        if reason:
            dropped[reason] += 1
            continue
        if record.get("_relationship_hints"):
            record["_relationship_hints"] = [
                h for h in record["_relationship_hints"] if h.get("source") not in DROPPED_HINTS
            ]
        prec = start_precision(raw)
        if prec is not None and prec < 9 and record.get("temporal_start") is not None:
            record["date_confidence"] = "low"  # decade, century or millennium
        sitelinks = int(raw.get("sitelinks") or 0)
        record["impact_score"] = impact_from_sitelinks(sitelinks)
        attrs = record.setdefault("attributes", {})
        attrs["_bulk"] = {"slice": s.id, "sitelinks": sitelinks}
        if raw.get("p31"):
            attrs["_p31"] = raw["p31"][:8]
        kept.append(record)
    return kept, dropped
