"""OHM Nominatim client — searches OpenHistoricalMap for entity matches.

Ported from api/app/Services/Ohm/OhmLookupService.php.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from ratelimit import limits, sleep_and_retry

from pipeline.config import settings

logger = logging.getLogger(__name__)

_OSM_TYPE_MAP: dict[str, str] = {
    "node": "node",
    "way": "way",
    "relation": "relation",
    "n": "node",
    "w": "way",
    "r": "relation",
}


def _normalize_name(value: str) -> str:
    """Lowercase, strip, collapse non-alnum to single space."""
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def _to_external_type(osm_type: str | None) -> str:
    if not osm_type:
        return "feature"
    return _OSM_TYPE_MAP.get(osm_type.lower(), "feature")


def _extract_match_label(item: dict[str, Any]) -> str | None:
    """Extract the best name from an OHM Nominatim result."""
    extratags = item.get("extratags") or {}
    name = extratags.get("name")
    if isinstance(name, str) and name:
        return name

    display_name = item.get("display_name")
    if not isinstance(display_name, str) or not display_name:
        return None

    segments = re.split(r"\s*,\s*", display_name)
    return segments[0] if segments else display_name


@sleep_and_retry
@limits(calls=settings.ohm_rpm, period=60)
def _rate_limited_get(url: str, params: dict[str, Any]) -> requests.Response:
    """HTTP GET with rate limiting."""
    return requests.get(
        url,
        params=params,
        timeout=settings.ohm_timeout,
        headers={"User-Agent": "WikiGlobe-Pipeline/1.0"},
    )


def search_by_name(
    name: str, location_name: str | None = None
) -> list[dict[str, Any]]:
    """Search OHM Nominatim by entity name, return normalized results.

    Mirrors OhmLookupService::searchByName().
    """
    query = name
    if location_name:
        query = f"{name} {location_name}"
    query = query.strip()

    url = f"{settings.ohm_nominatim_base_url}/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "polygon_geojson": 1,
        "extratags": 1,
    }

    try:
        resp = _rate_limited_get(url, params)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(f"OHM search failed for '{query}': {exc}")
        return []

    items = resp.json()
    if not isinstance(items, list):
        return []

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        results.append(_normalize_result(item))

    return results


def _normalize_result(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single OHM Nominatim response item.

    Mirrors OhmLookupService::normalizeLookupResult().
    """
    geojson = item.get("geojson")
    return {
        "external_type": _to_external_type(item.get("osm_type")),
        "external_id": str(item.get("osm_id", "")),
        "display_name": item.get("display_name"),
        "match_label": _extract_match_label(item),
        "geojson": geojson if isinstance(geojson, dict) else None,
        "external_tags": item.get("extratags") if isinstance(item.get("extratags"), dict) else {},
        "source_meta": {
            "display_name": item.get("display_name"),
            "class": item.get("class"),
            "type": item.get("type"),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
        },
    }
