"""Geo-resolver — produces _geo_resolution manifests for entities.

This module is the pipeline's decision-maker. It:
1. Queries OHM Nominatim for each entity name
2. Selects the best match using exact-name matching
3. Emits a `_geo_resolution` manifest dict

Ported decision logic from api/app/Actions/EntityGeoRef/AutoAttachOhmGeoRefAction.php.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.config import settings
from pipeline.wikidata.resolver.ohm_client import search_by_name, _normalize_name

logger = logging.getLogger(__name__)


def resolve(entity: dict[str, Any]) -> dict[str, Any]:
    """Resolve geo-reference for a single mapped entity.

    Returns the `_geo_resolution` manifest dict to attach to the entity record.
    """
    name = entity.get("name", "").strip()
    if not name:
        return _skipped("no_name")

    if not settings.ohm_enabled:
        return _skipped("ohm_disabled")

    location_name = entity.get("location_name")

    # ── Query OHM Nominatim ──────────────────────────────────────────────

    candidates = search_by_name(name, location_name)

    if not candidates:
        query = f"{name} {location_name}" if location_name else name
        return _no_match(
            resolver="ohm_nominatim",
            query=query.strip(),
            candidates=0,
            reason="no_candidates_returned",
        )

    # ── Select best match (exact normalized-name match) ──────────────────

    normalized_entity = _normalize_name(name)
    query_used = f"{name} {location_name}" if location_name else name
    best = None

    for candidate in candidates:
        label = candidate.get("match_label") or candidate.get("display_name") or ""
        if _normalize_name(label) == normalized_entity:
            best = candidate
            break

    if best is None:
        return _no_match(
            resolver="ohm_nominatim",
            query=query_used.strip(),
            candidates=len(candidates),
            reason="no_exact_name_match",
        )

    if not best.get("external_id"):
        return _no_match(
            resolver="ohm_nominatim",
            query=query_used.strip(),
            candidates=len(candidates),
            reason="best_match_missing_id",
        )

    # ── Build match score ────────────────────────────────────────────────

    match_label = best.get("match_label") or best.get("display_name") or ""
    score = 1.0 if _normalize_name(match_label) == normalized_entity else 0.0

    # ── Build manifest ───────────────────────────────────────────────────

    manifest: dict[str, Any] = {
        "status": "matched",
        "geo_ref": {
            "provider": "ohm",
            "external_type": best["external_type"],
            "external_id": best["external_id"],
            "match_role": "primary",
            "retrieval_method": "nominatim",
            "match_score": score,
            "external_tags": best.get("external_tags") or {},
            "source_meta": best.get("source_meta") or {},
        },
        "provenance": {
            "resolver": "ohm_nominatim",
            "query": query_used.strip(),
            "candidates": len(candidates),
            "reason": "exact_name_match",
        },
    }

    geojson = best.get("geojson")
    if isinstance(geojson, dict) and geojson.get("type") and geojson.get("coordinates"):
        manifest["geometry"] = geojson

    return manifest


def resolve_batch(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve geo-references for a batch of entities.

    Mutates each entity dict in-place by adding `_geo_resolution` key.
    Returns the same list for chaining.
    """
    for entity in entities:
        entity["_geo_resolution"] = resolve(entity)

    matched = sum(1 for e in entities if e.get("_geo_resolution", {}).get("status") == "matched")
    logger.info(f"Geo-resolved {matched}/{len(entities)} entities")

    return entities


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "provenance": {
            "resolver": "ohm_nominatim",
            "query": None,
            "candidates": 0,
            "reason": reason,
        },
    }


def _no_match(*, resolver: str, query: str, candidates: int, reason: str) -> dict[str, Any]:
    return {
        "status": "no_match",
        "provenance": {
            "resolver": resolver,
            "query": query,
            "candidates": candidates,
            "reason": reason,
        },
    }
