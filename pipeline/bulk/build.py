"""Raw Wikidata items -> import records, with each slice's quality gates."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from pipeline.bulk.fetch import DATE_PROPS
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


# Wikidata time precision: 9 year, 8 decade, 7 century, 6 millennium. A
# century value comes back as a bare year (901 or 1000), so a person "born in
# the 10th century" reads as born in 901 exactly: Roman lives of -101..100,
# reigns from 800, deaths in 2000, children born before their parents. People
# drop such dates (the row stays undated, or `require: dates` drops it);
# places and events keep them as low-confidence era markers.
COARSE_PRECISION = 7
# A recorded lifespan beyond this is a data error (a traditional birth year, or
# a wrong birth or death value); the oldest verified people lived 115-122 years.
MAX_LIFESPAN = 115
RAW_KEY_PIDS: dict[str, list[str]] = {}
for _pid, _key in DATE_PROPS:
    RAW_KEY_PIDS.setdefault(_key, []).append(_pid)


def drop_coarse_dates(raw: dict[str, Any]) -> dict[str, Any]:
    """The raw item without its century-or-coarser dates (and their properties)."""
    precs = raw.get("_date_prec") or {}
    coarse = {k for k, p in precs.items() if p <= COARSE_PRECISION and raw.get(k) is not None}
    if not coarse:
        return raw
    out = {k: v for k, v in raw.items() if k not in coarse}
    out["_date_prec"] = {k: p for k, p in precs.items() if k not in coarse}
    drop_pids = {pid for k in coarse for pid in RAW_KEY_PIDS.get(k, [])}
    out["properties"] = {k: v for k, v in (raw.get("properties") or {}).items() if k not in drop_pids}
    return out


def drop_dates(raw: dict[str, Any]) -> dict[str, Any]:
    """The raw item without any of its dates (and their properties)."""
    keys = {k for k in RAW_KEY_PIDS if raw.get(k) is not None}
    out = {k: v for k, v in raw.items() if k not in keys}
    out["_date_prec"] = {}
    drop_pids = {pid for pids in RAW_KEY_PIDS.values() for pid in pids}
    out["properties"] = {k: v for k, v in (raw.get("properties") or {}).items() if k not in drop_pids}
    return out


def bad_lifespan(record: dict[str, Any]) -> bool:
    """Whether a person's death precedes their birth or comes implausibly late."""
    start, end = _year(record.get("temporal_start")), _year(record.get("temporal_end"))
    return start is not None and end is not None and (end < start or end - start > MAX_LIFESPAN)


def low_precision(raw: dict[str, Any]) -> bool:
    """Whether any date the row keeps is coarser than a year."""
    precs = raw.get("_date_prec") or {}
    return any(p < 9 for k, p in precs.items() if raw.get(k) is not None)


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
        if s.entity_type == "person":
            raw = drop_coarse_dates(raw)
        if HATNOTE.search(raw.get("summary") or ""):
            raw = {k: v for k, v in raw.items() if k not in ("summary", "full_extract")}
        record = mapper.map(raw, s.entity_type)
        if record is not None and s.entity_type == "person" and bad_lifespan(record):
            # A real person with a contradictory lifespan: keep them undated.
            raw = drop_dates(raw)
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
        if low_precision(raw) and (record.get("temporal_start") or record.get("temporal_end")) is not None:
            record["date_confidence"] = "low"  # decade, century or millennium
        sitelinks = int(raw.get("sitelinks") or 0)
        record["impact_score"] = impact_from_sitelinks(sitelinks)
        attrs = record.setdefault("attributes", {})
        attrs["_bulk"] = {"slice": s.id, "sitelinks": sitelinks}
        if raw.get("p31"):
            attrs["_p31"] = raw["p31"][:8]
        kept.append(record)
    return kept, dropped
