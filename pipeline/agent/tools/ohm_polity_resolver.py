"""OHM-first polity resolution (hybrid: live Nominatim + local cache).

For a polity name the LLM extracted (e.g. "Byzantine Empire"), find the
contextually-relevant OpenHistoricalMap feature — even when OHM's canonical name
differs ("Imperium Romanum Orientale", 752-798) — and return its OHM id, name,
geometry and a `_geo_resolution` manifest. Callers adopt OHM's canonical name +
id for the entity.

Hybrid: each unique name is queried against OHM Nominatim once, then its full
candidate list is cached in SQLite; era selection happens locally from the
cached candidates, so different transcripts/eras reuse one API call.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

_POINT_WKT_RE = re.compile(r"point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", re.IGNORECASE)

from pipeline.agent.log_config import get_logger
from pipeline.agent.tools.disambiguation import era_year
from pipeline.wikidata.resolver.ohm_client import search_by_name, _normalize_name

logger = get_logger(__name__)

_CACHE_PATH = Path("output/ohm_collections/ohm_polity_cache.sqlite")
_ACCEPT_THRESHOLD = 0.3


# ── candidate scoring (pure) ─────────────────────────────────────────────────

def _name_tokens(value: str | None) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if len(t) >= 3}


def _candidate_era(candidate: dict[str, Any]) -> tuple[int | None, int | None]:
    tags = candidate.get("external_tags") or {}
    return era_year(tags.get("start_date")), era_year(tags.get("end_date"))


def _era_distance(target: int | None, start: int | None, end: int | None) -> int | None:
    """Years between `target` and the candidate's [start, end] span (0 = inside)."""
    if target is None or (start is None and end is None):
        return None
    lo = start if start is not None else end
    hi = end if end is not None else start
    if lo is not None and hi is not None and lo <= target <= hi:
        return 0
    bounds = [abs(target - b) for b in (lo, hi) if b is not None]
    return min(bounds) if bounds else None


def _era_fit(target: int | None, candidate: dict[str, Any]) -> float:
    # OHM models empires as many short boundary snapshots (e.g. Imperium Romanum
    # 116-117), so "near" should score generously — the right polity rarely has a
    # snapshot on the exact queried year.
    dist = _era_distance(target, *_candidate_era(candidate))
    if dist is None:
        return 0.5  # unknown era — neutral
    if dist == 0:
        return 1.0
    if dist <= 50:
        return 0.85
    if dist <= 150:
        return 0.7
    if dist <= 500:
        return 0.45
    return max(0.0, 1.0 - dist / 2000.0)


def relevance(candidate: dict[str, Any], query: str, target_era: int | None,
              entity_wikidata: str | None = None) -> float:
    """0..1 relevance of an OHM candidate to a polity query in its era context.

    A Wikidata-id match is decisive (1.0); otherwise blend name-token overlap
    with era fit. Name overlap can be 0 when OHM uses a different language for
    the canonical name — era then carries the match (the user's "find what OHM
    has that's relevant for the context").
    """
    label = candidate.get("match_label") or candidate.get("display_name") or ""
    if _normalize_name(label) == _normalize_name(query):
        name_sim = 1.0
    else:
        qt, lt = _name_tokens(query), _name_tokens(label)
        name_sim = len(qt & lt) / len(qt | lt) if (qt and lt) else 0.0

    wd = (candidate.get("external_tags") or {}).get("wikidata")
    if entity_wikidata and wd and wd == entity_wikidata:
        return 1.0

    return round(0.55 * name_sim + 0.45 * _era_fit(target_era, candidate), 3)


def best_candidate(candidates: list[dict[str, Any]], query: str, target_era: int | None,
                   entity_wikidata: str | None = None) -> dict[str, Any] | None:
    """Pick the most relevant candidate; None if none clears the threshold."""
    scored = [
        (relevance(c, query, target_era, entity_wikidata), c)
        for c in candidates
        if c.get("external_id")
    ]
    if not scored:
        return None
    scored.sort(key=lambda sc: sc[0], reverse=True)
    score, candidate = scored[0]
    if score < _ACCEPT_THRESHOLD:
        return None
    return {**candidate, "match_score": score}


def build_manifest(candidate: dict[str, Any], query: str, candidate_count: int) -> dict[str, Any]:
    """Build the `_geo_resolution` manifest consumed by ImportGeoResolutionAction."""
    manifest: dict[str, Any] = {
        "status": "matched",
        "geo_ref": {
            "provider": "ohm",
            "external_type": candidate["external_type"],
            "external_id": str(candidate["external_id"]),
            "match_role": "primary",
            "retrieval_method": "nominatim",
            "match_score": float(candidate.get("match_score", 0.0)),
            "external_tags": candidate.get("external_tags") or {},
            "source_meta": candidate.get("source_meta") or {},
        },
        "provenance": {
            "resolver": "ohm_nominatim",
            "query": query,
            "candidates": candidate_count,
            "reason": "ohm_first_polity",
        },
    }
    geojson = candidate.get("geojson")
    if isinstance(geojson, dict) and geojson.get("type") and geojson.get("coordinates"):
        manifest["geometry"] = geojson
    return manifest


def parse_point_wkt(value: Any) -> tuple[float, float] | None:
    """Parse a Wikidata-style 'Point(lon lat)' string into (lon, lat)."""
    if not isinstance(value, str):
        return None
    m = _POINT_WKT_RE.search(value)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def build_wikidata_point_manifest(qid: str | None, coords_wkt: Any) -> dict[str, Any] | None:
    """Approximate-point fallback when OHM has no feature for a polity.

    Uses the entity's Wikidata coordinate (P625) so the polity still gets an
    approximate location on the map. Persisted as a wikidata geo-ref (fallback
    role) — not an OHM border.
    """
    lonlat = parse_point_wkt(coords_wkt)
    if not qid or not lonlat:
        return None
    lon, lat = lonlat
    return {
        "status": "matched",
        "geo_ref": {
            "provider": "wikidata",
            "external_type": "qid",
            "external_id": str(qid),
            "match_role": "fallback",
            "retrieval_method": "rest",
            "match_score": 0.5,
            "external_tags": {},
            "source_meta": {"source": "wikidata_p625"},
        },
        "provenance": {"resolver": "wikidata_coords", "reason": "ohm_miss_approximate_point"},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


# ── cache (hybrid) ───────────────────────────────────────────────────────────

def _cache_connect(cache_path: Path) -> sqlite3.Connection | None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(cache_path, timeout=10)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ohm_search_cache "
            "(normalized_name TEXT PRIMARY KEY, candidates_json TEXT NOT NULL)"
        )
        return conn
    except sqlite3.Error as exc:
        logger.warning("OHM cache unavailable (%s); falling back to live-only", exc)
        return None


def _cached_search(name: str, location_name: str | None, cache_path: Path) -> list[dict[str, Any]]:
    """Return OHM candidates for `name`, from cache or a single live query."""
    key = _normalize_name(name)
    conn = _cache_connect(cache_path)
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT candidates_json FROM ohm_search_cache WHERE normalized_name = ?", (key,)
            ).fetchone()
            if row is not None:
                conn.close()
                return json.loads(row[0])
        except (sqlite3.Error, json.JSONDecodeError):
            pass

    candidates = search_by_name(name, location_name)

    if conn is not None:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO ohm_search_cache (normalized_name, candidates_json) VALUES (?, ?)",
                (key, json.dumps(candidates, default=str)),
            )
            conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return candidates


# ── public entry point ───────────────────────────────────────────────────────

def resolve_polity(
    name: str,
    era_year_hint: int | None = None,
    location_name: str | None = None,
    entity_wikidata: str | None = None,
    cache_path: Path | None = None,
) -> dict[str, Any] | None:
    """Resolve a polity name to its contextually-best OHM feature.

    Returns {name, external_id, external_type, wikidata_id, manifest} or None.
    """
    if not name or not name.strip():
        return None

    candidates = _cached_search(name.strip(), location_name, cache_path or _CACHE_PATH)
    if not candidates:
        return None

    best = best_candidate(candidates, name, era_year_hint, entity_wikidata)
    if best is None:
        return None

    return {
        "name": best.get("match_label") or best.get("display_name") or name,
        "external_id": str(best["external_id"]),
        "external_type": best["external_type"],
        "wikidata_id": (best.get("external_tags") or {}).get("wikidata"),
        "match_score": best.get("match_score", 0.0),
        "manifest": build_manifest(best, name.strip(), len(candidates)),
    }
