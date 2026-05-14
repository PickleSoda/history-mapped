"""Enrich OHM relation candidates with target Wikidata and Wikipedia metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pipeline.ohm_borders.enricher import batch_enrich_qids, search_qid_by_name
from pipeline.wikidata.mapper.relationship_mapper import get_inverse, get_relationship_type
from pipeline.wikidata.scraper.wikipedia import WikipediaEnricher

_SOURCE_TAG_PROPERTY_MAP = {
    "predecessor": "P155",
    "preceded_by": "P155",
    "successor": "P156",
    "succeeded_by": "P156",
    "start_event": "P828",
    "end_event": "P1542",
}


def enrich_relation_candidates(
    candidates: list[dict[str, Any]],
    *,
    metadata_fetcher: Any = batch_enrich_qids,
    name_searcher: Any = search_qid_by_name,
    wikipedia_enricher: Any | None = None,
) -> list[dict[str, Any]]:
    wikipedia = wikipedia_enricher or WikipediaEnricher()

    normalized: list[dict[str, Any]] = []
    target_keys: list[tuple[str | None, str | None]] = []
    qids_to_fetch: list[str] = []

    for candidate in candidates:
        source_tag_key = candidate.get("source_tag_key")
        wikidata_property = _SOURCE_TAG_PROPERTY_MAP.get(str(source_tag_key or ""))
        relationship_type = get_relationship_type(wikidata_property) if wikidata_property else candidate.get("relationship_type")
        inverse_relationship_type = get_inverse(relationship_type) if isinstance(relationship_type, str) else None
        target_wikidata_id = _normalize_optional_string(candidate.get("target_wikidata_id"))
        target_label = _normalize_optional_string(candidate.get("target_label"))

        if target_wikidata_id is None and target_label is not None:
            target_wikidata_id = name_searcher(target_label)

        enriched_candidate = {
            **candidate,
            "relationship_type": relationship_type,
            "inverse_relationship_type": inverse_relationship_type,
            "target_wikidata_id": target_wikidata_id,
            "source": f"wikidata:{wikidata_property}" if wikidata_property else None,
        }
        normalized.append(enriched_candidate)

        target_key = (target_wikidata_id, target_label)
        target_keys.append(target_key)
        if target_wikidata_id is not None:
            qids_to_fetch.append(target_wikidata_id)

    metadata_by_qid = metadata_fetcher(list(dict.fromkeys(qids_to_fetch))) if qids_to_fetch else {}

    unique_entities: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    wikipedia_items: list[dict[str, Any]] = []
    wikipedia_order: list[tuple[str | None, str | None]] = []

    for candidate, target_key in zip(normalized, target_keys):
        if target_key in unique_entities:
            continue

        target_wikidata_id, target_label = target_key
        metadata = metadata_by_qid.get(target_wikidata_id, {}) if target_wikidata_id else {}
        entity = _build_target_entity(
            metadata=metadata,
            target_wikidata_id=target_wikidata_id,
            target_label=target_label,
            relationship_type=str(candidate.get("relationship_type") or ""),
            source_tag_key=str(candidate.get("source_tag_key") or ""),
        )
        unique_entities[target_key] = entity
        wikipedia_items.append(deepcopy(entity))
        wikipedia_order.append(target_key)

    if wikipedia_items:
        enriched_items = wikipedia.enrich_batch(wikipedia_items)
        for key, enriched_item in zip(wikipedia_order, enriched_items):
            entity = unique_entities[key]
            if enriched_item.get("summary"):
                entity["summary"] = enriched_item["summary"]
            if enriched_item.get("full_extract"):
                entity.setdefault("attributes", {})["wikipedia_extract"] = enriched_item["full_extract"]
            if enriched_item.get("infobox"):
                entity.setdefault("attributes", {})["infobox"] = enriched_item["infobox"]

    enriched: list[dict[str, Any]] = []
    for candidate, target_key in zip(normalized, target_keys):
        enriched.append({
            **candidate,
            "target_entity": deepcopy(unique_entities[target_key]),
        })

    return enriched



def _build_target_entity(
    *,
    metadata: dict[str, Any],
    target_wikidata_id: str | None,
    target_label: str | None,
    relationship_type: str,
    source_tag_key: str,
) -> dict[str, Any]:
    name = _normalize_optional_string(metadata.get("name_en")) or target_label or target_wikidata_id or "Unknown relation target"
    summary = _normalize_optional_string(metadata.get("description"))
    entity_type, entity_group = _infer_target_type(name, summary, relationship_type, source_tag_key)

    entity: dict[str, Any] = {
        "name": name,
        "entity_type": entity_type,
        "entity_group": entity_group,
        "wikidata_id": target_wikidata_id,
        "summary": summary,
        "alternative_names": list(metadata.get("aliases_en") or []),
        "temporal_start": _normalize_optional_string(metadata.get("temporal_start")),
        "temporal_end": _normalize_optional_string(metadata.get("temporal_end")),
        "verification_status": "pipeline_draft",
        "confidence": "medium",
        "source_citations": ([{"source": "wikidata", "wikidata_id": target_wikidata_id}] if target_wikidata_id else []),
        "attributes": {},
    }

    wikipedia_title = _normalize_optional_string(metadata.get("wikipedia_title"))
    if wikipedia_title is not None:
        entity["attributes"]["wikipedia_title"] = wikipedia_title

    if not entity["attributes"]:
        entity.pop("attributes")

    return entity



def _infer_target_type(name: str, summary: str | None, relationship_type: str, source_tag_key: str) -> tuple[str, str]:
    haystack = f"{name} {summary or ''}".lower()

    if relationship_type in {"preceded_by", "succeeded_by"}:
        return "political_entity", "POLITY"

    if "treaty" in haystack or "agreement" in haystack:
        return "event_treaty", "EVENT"

    if any(token in haystack for token in ("revolution", "rebellion", "uprising")):
        return "event_rebellion", "EVENT"

    if any(token in haystack for token in ("war", "battle", "siege", "campaign")):
        return "event_war", "EVENT"

    if source_tag_key in {"start_event", "end_event"}:
        return "event_war", "EVENT"

    return "political_entity", "POLITY"



def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    return trimmed or None
