from __future__ import annotations

from typing import Any, Callable

from pipeline.ohm_borders.enricher import batch_enrich_qids, search_qid_by_name
from pipeline.wikidata.resolver.geo_resolver import resolve as resolve_geo


def enrich_candidate(
    candidate: dict[str, Any],
    *,
    name_searcher: Callable[[str], str | None] = search_qid_by_name,
    metadata_enricher: Callable[[list[str]], dict[str, dict[str, Any]]] = batch_enrich_qids,
    geo_resolver: Callable[[dict[str, Any]], dict[str, Any]] = resolve_geo,
) -> dict[str, Any]:
    enriched = dict(candidate)
    wikidata_id = _normalize_optional_string(enriched.get("wikidata_id"))
    match_source = "existing_qid"

    if wikidata_id is None:
        resolved_qid = name_searcher(str(enriched.get("name") or ""))
        if _normalize_optional_string(resolved_qid):
            wikidata_id = _normalize_optional_string(resolved_qid)
            enriched["wikidata_id"] = wikidata_id
            match_source = "name_search"
        else:
            match_source = "name_search_unmatched"

    enriched["_wikidata_match_source"] = match_source

    if wikidata_id is not None:
        metadata = metadata_enricher([wikidata_id]).get(wikidata_id, {})
        enriched = _merge_metadata(enriched, metadata)

    geo_resolution_input = {
        **enriched,
        "name": _normalize_optional_string(enriched.get("name")) or "",
    }
    geo_resolution = geo_resolver(geo_resolution_input)
    enriched["_geo_resolution"] = geo_resolution
    geometry = geo_resolution.get("geometry") if isinstance(geo_resolution, dict) else None
    enriched["fallback_geojson"] = geometry if isinstance(geometry, dict) else None
    return enriched


def _merge_metadata(candidate: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(candidate)

    if metadata.get("name_en") and not enriched.get("name"):
        enriched["name"] = metadata["name_en"]
    if metadata.get("description") and not enriched.get("summary"):
        enriched["summary"] = metadata["description"]
    if metadata.get("aliases_en") and not enriched.get("alternative_names"):
        enriched["alternative_names"] = metadata["aliases_en"]

    return enriched


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None