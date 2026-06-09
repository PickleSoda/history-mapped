import json
import logging
from pathlib import Path
from typing import Any

import requests

from pipeline.wikidata.collections.artifacts import (
    collection_artifact_dir,
    entities_final_path,
    included_report_path,
    excluded_report_path,
    manifest_path,
    ensure_dirs,
)
from pipeline.wikidata.mapper.entity_mapper import EntityMapper
from pipeline.wikidata.dedup.deduplicator import Deduplicator

logger = logging.getLogger(__name__)

EGYPT_DOMAIN_QIDS = {"Q79", "Q11768"}

CATEGORY_TO_ENTITY_TYPE: dict[str, str] = {
    "modern_state": "political_entity",
    "ancient_civilization": "political_entity",
    "kingdom": "political_entity",
    "province": "political_entity",
    "sultanate": "political_entity",
    "khedivate": "political_entity",
    "republic": "political_entity",
    "place": "city",
    "person": "person",
    "event_battle": "event_battle",
    "event_war": "event_war",
}

# Properties that indicate Egypt domain (for expansion filtering)
EGYPT_DOMAIN_PROPERTIES = {"P17", "P30", "P131", "P276"}

# Properties that link people/events to Egypt entities (for expansion)
EXPANSION_LINK_PROPERTIES = {"P39", "P106", "P607", "P1344", "P710"}

# Properties that link wars/battles to people
WAR_PARTICIPANT_PROPERTIES = {"P710", "P726"}

# Properties that link people to wars/battles
PERSON_CONFLICT_PROPERTIES = {"P607", "P1344"}


def batch_fetch_wikidata(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch Wikidata entity data by QID using wbgetentities API.

    Returns a dict keyed by QID with data formatted for EntityMapper.
    """
    results: dict[str, dict[str, Any]] = {}
    if not qids:
        return results

    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "format": "json",
            "languages": "en",
            "props": "labels|descriptions|aliases|claims|sitelinks",
        }
        try:
            resp = requests.get(
                "https://www.wikidata.org/w/api.php",
                params=params,
                timeout=45,
                headers={"User-Agent": "history-mapped-Pipeline/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(f"Wikidata batch fetch failed for chunk starting at {i}: {exc}")
            continue

        for qid, entity in data.get("entities", {}).items():
            if entity.get("missing") is not None:
                continue
            mapped = _transform_wikidata_entity(qid, entity)
            if mapped:
                results[qid] = mapped

    return results


def _transform_wikidata_entity(qid: str, entity: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a Wikidata API entity response into EntityMapper input format."""
    labels = entity.get("labels", {})
    en_label = labels.get("en", {}).get("value", "") if isinstance(labels, dict) else ""
    if not en_label:
        return None

    descriptions = entity.get("descriptions", {})
    en_desc = descriptions.get("en", {}).get("value", "") if isinstance(descriptions, dict) else ""

    aliases = entity.get("aliases", {})
    alias_list: list[str] = []
    if isinstance(aliases, dict):
        en_aliases = aliases.get("en", [])
        if isinstance(en_aliases, list):
            alias_list = [a.get("value", "") for a in en_aliases if isinstance(a, dict)]

    claims = entity.get("claims", {})
    if not isinstance(claims, dict):
        claims = {}

    coords = _extract_coords_from_claims(claims)
    inception = _extract_date_from_claims(claims, "P571")
    dissolution = _extract_date_from_claims(claims, "P576")
    start_time = _extract_date_from_claims(claims, "P580")
    end_time = _extract_date_from_claims(claims, "P582")
    point_in_time = _extract_date_from_claims(claims, "P585")
    birth_date = _extract_date_from_claims(claims, "P569")
    death_date = _extract_date_from_claims(claims, "P570")

    properties = _extract_properties_from_claims(claims)
    p31_qids = _extract_p31_qids(claims)
    location_name = _derive_location_name(properties)

    sitelinks = entity.get("sitelinks", {})
    wp_title = None
    if isinstance(sitelinks, dict):
        enwiki = sitelinks.get("enwiki", {})
        if isinstance(enwiki, dict):
            wp_title = enwiki.get("title")

    return {
        "qid": qid,
        "label": en_label,
        "description": en_desc,
        "aliases": alias_list,
        "coords": coords,
        "inception": inception,
        "dissolution": dissolution,
        "start_time": start_time,
        "end_time": end_time,
        "point_in_time": point_in_time,
        "birth_date": birth_date,
        "death_date": death_date,
        "location_name": location_name,
        "wikipedia_title": wp_title,
        "properties": properties,
        "_p31_qids": list(p31_qids),
    }


def _extract_p31_qids(claims: dict[str, Any]) -> set[str]:
    """Extract P31 (instance of) QIDs from claims."""
    qids: set[str] = set()
    for claim in claims.get("P31", []):
        if not isinstance(claim, dict):
            continue
        mainsnak = claim.get("mainsnak", {})
        if not isinstance(mainsnak, dict):
            continue
        datavalue = mainsnak.get("datavalue", {})
        if not isinstance(datavalue, dict):
            continue
        value = datavalue.get("value", {})
        if isinstance(value, dict):
            qid = value.get("id")
            if qid:
                qids.add(qid)
    return qids


def _extract_coords_from_claims(claims: dict[str, Any]) -> dict[str, float] | None:
    """Extract coordinates from P625 claims."""
    for claim in claims.get("P625", []):
        if not isinstance(claim, dict):
            continue
        mainsnak = claim.get("mainsnak", {})
        if not isinstance(mainsnak, dict):
            continue
        datavalue = mainsnak.get("datavalue", {})
        if not isinstance(datavalue, dict):
            continue
        value = datavalue.get("value", {})
        if isinstance(value, dict):
            lat = value.get("latitude")
            lon = value.get("longitude")
            if lat is not None and lon is not None:
                return {"lat": float(lat), "lon": float(lon)}
    return None


def _extract_date_from_claims(claims: dict[str, Any], prop: str) -> str | None:
    """Extract a year string from a date claim."""
    for claim in claims.get(prop, []):
        if not isinstance(claim, dict):
            continue
        mainsnak = claim.get("mainsnak", {})
        if not isinstance(mainsnak, dict):
            continue
        datavalue = mainsnak.get("datavalue", {})
        if not isinstance(datavalue, dict):
            continue
        value = datavalue.get("value", {})
        if isinstance(value, dict):
            time_val = value.get("time")
            if time_val:
                # Parse "+YYYY-MM-DDT00:00:00Z" or "-YYYY-MM-DDT00:00:00Z"
                try:
                    if time_val.startswith("-"):
                        year = "-" + time_val[1:].split("-")[0]
                    else:
                        year = time_val[1:].split("-")[0] if time_val.startswith("+") else time_val.split("-")[0]
                    return str(int(year))
                except (ValueError, IndexError):
                    pass
    return None


def _extract_properties_from_claims(claims: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Extract relationship properties from claims in EntityMapper format."""
    props: dict[str, list[dict[str, Any]]] = {}
    for prop_id, statements in claims.items():
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, dict):
                continue
            mainsnak = statement.get("mainsnak", {})
            if not isinstance(mainsnak, dict):
                continue
            datavalue = mainsnak.get("datavalue", {})
            if not isinstance(datavalue, dict):
                continue
            value = datavalue.get("value", {})
            if not isinstance(value, dict):
                continue
            val_type = value.get("entity-type")
            if val_type == "item":
                qid = value.get("id")
                if qid:
                    entry = {"qid": qid, "label": "", "uri": f"http://www.wikidata.org/entity/{qid}"}
                    props.setdefault(prop_id, []).append(entry)
    return props


def _derive_location_name(properties: dict[str, list[dict[str, Any]]]) -> str | None:
    """Derive location name from P17, P131, P276 properties."""
    for prop in ("P276", "P131", "P17"):
        for entry in properties.get(prop, []):
            label = entry.get("label", "")
            if label:
                return label
    return None


def fetch_seed_entities(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qids = [s["qid"] for s in seeds]
    raw = batch_fetch_wikidata(qids)
    mapper = EntityMapper()
    records: list[dict[str, Any]] = []
    for seed in seeds:
        qid = seed["qid"]
        if qid not in raw:
            continue
        entity_type = CATEGORY_TO_ENTITY_TYPE.get(seed.get("category", ""), "political_entity")
        mapped = mapper.map(raw[qid], entity_type)
        if mapped is None:
            continue
        mapped["_seed_qid"] = qid
        mapped["_seed_category"] = seed.get("category", "unknown")
        records.append(mapped)
    return records


def apply_bounded_expansion(
    included: list[dict[str, Any]],
    expansion_qids: list[str],
) -> list[dict[str, Any]]:
    if not expansion_qids:
        return []

    raw = batch_fetch_wikidata(expansion_qids)
    mapper = EntityMapper()
    expanded: list[dict[str, Any]] = []

    for qid, item in raw.items():
        if not _is_egypt_domain(item):
            continue
        # Determine entity type from properties
        entity_type = _infer_entity_type_from_properties(item)
        mapped = mapper.map(item, entity_type)
        if mapped is None:
            continue
        mapped["_expansion_from"] = _find_source_qid(item, included)
        expanded.append(mapped)

    return expanded


def _infer_entity_type_from_properties(item: dict[str, Any]) -> str:
    """Infer entity type from P31 (instance of) QIDs.

    Uses the _p31_qids field extracted during batch_fetch_wikidata.
    """
    p31_qids = set(item.get("_p31_qids", []))

    # Human
    if "Q5" in p31_qids:
        return "person"

    # Battles and wars
    battle_classes = {"Q178561", "Q188055", "Q1261499", "Q180684", "Q645883"}
    if p31_qids & battle_classes:
        return "event_battle"

    war_classes = {"Q198", "Q831663", "Q350604", "Q104212151"}
    if p31_qids & war_classes:
        return "event_war"

    # City-related classes
    city_classes = {"Q515", "Q1549591", "Q15661340", "Q40364446", "Q148837", "Q486972", "Q3957", "Q532"}
    if p31_qids & city_classes:
        return "city"

    # Historical/political classes
    polity_classes = {
        "Q3624078", "Q48349", "Q133442", "Q3024240", "Q28171280",
        "Q208281", "Q1063239", "Q12097", "Q105543609", "Q6256",
        "Q7275", "Q28513", "Q331644", "Q170770", "Q79007",
        "Q170156", "Q164142", "Q3241965", "Q208164", "Q1763527",
        "Q8432",
    }
    if p31_qids & polity_classes:
        return "political_entity"

    return "political_entity"


def _is_egypt_domain(item: dict[str, Any]) -> bool:
    """Check if item is linked to Egypt via location or structural properties.

    Works with both raw Wikidata claims and mapped properties format.
    An entity is considered Egypt-domain if:
    1. It is located in Egypt (P17/P30/P131/P276)
    2. It holds a position in Egypt (P39)
    3. It is a participant in an Egypt-related event (P607/P1344)
    """
    linked_qids: set[str] = set()

    # Try raw claims first
    claims = item.get("claims", {})
    if isinstance(claims, dict):
        # Location properties
        for prop in EGYPT_DOMAIN_PROPERTIES:
            for claim in claims.get(prop, []):
                if not isinstance(claim, dict):
                    continue
                mainsnak = claim.get("mainsnak", {})
                if not isinstance(mainsnak, dict):
                    continue
                datavalue = mainsnak.get("datavalue", {})
                if not isinstance(datavalue, dict):
                    continue
                value = datavalue.get("value", {})
                if isinstance(value, dict):
                    qid = value.get("id")
                    if qid:
                        linked_qids.add(qid)

        # Structural properties (position, participant, etc.)
        for prop in EXPANSION_LINK_PROPERTIES:
            for claim in claims.get(prop, []):
                if not isinstance(claim, dict):
                    continue
                mainsnak = claim.get("mainsnak", {})
                if not isinstance(mainsnak, dict):
                    continue
                datavalue = mainsnak.get("datavalue", {})
                if not isinstance(datavalue, dict):
                    continue
                value = datavalue.get("value", {})
                if isinstance(value, dict):
                    qid = value.get("id")
                    if qid:
                        linked_qids.add(qid)

    # Fallback to mapped properties
    properties = item.get("properties", {})
    if isinstance(properties, dict):
        for prop in EGYPT_DOMAIN_PROPERTIES | EXPANSION_LINK_PROPERTIES:
            for entry in properties.get(prop, []):
                if isinstance(entry, dict):
                    qid = entry.get("qid")
                    if qid:
                        linked_qids.add(qid)

    return bool(linked_qids & EGYPT_DOMAIN_QIDS)


def _find_source_qid(item: dict[str, Any], included: list[dict[str, Any]]) -> str | None:
    """Find which included QID the item links to via structural properties.

    Works with both raw Wikidata claims and mapped properties format.
    """
    included_qids = {i.get("wikidata_id") for i in included if i.get("wikidata_id")}
    all_link_props = EGYPT_DOMAIN_PROPERTIES | EXPANSION_LINK_PROPERTIES | WAR_PARTICIPANT_PROPERTIES | PERSON_CONFLICT_PROPERTIES | {"P361", "P527"}

    # Try raw claims first
    claims = item.get("claims", {})
    if isinstance(claims, dict):
        for prop in all_link_props:
            for claim in claims.get(prop, []):
                if not isinstance(claim, dict):
                    continue
                mainsnak = claim.get("mainsnak", {})
                if not isinstance(mainsnak, dict):
                    continue
                datavalue = mainsnak.get("datavalue", {})
                if not isinstance(datavalue, dict):
                    continue
                value = datavalue.get("value", {})
                if isinstance(value, dict):
                    qid = value.get("id")
                    if qid in included_qids:
                        return qid

    # Fallback to mapped properties
    properties = item.get("properties", {})
    if isinstance(properties, dict):
        for prop in all_link_props:
            for entry in properties.get(prop, []):
                if isinstance(entry, dict):
                    qid = entry.get("qid")
                    if qid in included_qids:
                        return qid

    return None


def _expand_rules_hints_to_countries(records: list[dict[str, Any]]) -> None:
    """Expand 'rules' relationship hints to include the country of the position.

    P39 (position held) points to a position like Q37110 (pharaoh).
    The position itself has P17 (country) = Q11768 (Ancient Egypt).
    This function fetches P17 for each unique position QID and adds
    additional 'rules' hints pointing to the country.
    """
    position_qids: set[str] = set()
    for record in records:
        for hint in record.get("_relationship_hints", []):
            if hint.get("relationship_type") == "rules":
                position_qids.add(hint["target_wikidata_id"])

    if not position_qids:
        return

    position_qids.discard("")

    country_map: dict[str, str] = {}
    for i in range(0, len(position_qids), 50):
        chunk = list(position_qids)[i:i + 50]
        try:
            resp = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "format": "json",
                    "props": "claims",
                    "languages": "en",
                },
                headers={"User-Agent": "history-mapped-Pipeline/1.0"},
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()
            for qid, entity in data.get("entities", {}).items():
                claims = entity.get("claims", {})
                p17_claims = claims.get("P17", [])
                if p17_claims:
                    for claim in p17_claims:
                        mainsnak = claim.get("mainsnak", {})
                        dv = mainsnak.get("datavalue", {})
                        val = dv.get("value", {})
                        if isinstance(val, dict) and val.get("id"):
                            country_map[qid] = val["id"]
                            break
        except Exception as exc:
            logger.warning(f"Failed to fetch P17 for positions: {exc}")

    if not country_map:
        return

    for record in records:
        hints = record.get("_relationship_hints", [])
        new_hints = []
        for hint in hints:
            if hint.get("relationship_type") == "rules":
                pos_qid = hint["target_wikidata_id"]
                country_qid = country_map.get(pos_qid)
                if country_qid:
                    new_hints.append({
                        "relationship_type": "rules",
                        "target_wikidata_id": country_qid,
                        "target_label": "",
                        "confidence": "medium",
                        "source": f"wikidata:P39->P17",
                    })
        hints.extend(new_hints)


def build_collection_artifacts(
    artifact_dir: Path,
    records: list[dict[str, Any]],
    seeds: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> None:
    ensure_dirs(artifact_dir)

    _expand_rules_hints_to_countries(records)

    deduplicator = Deduplicator()
    deduped = deduplicator.deduplicate(records)

    with open(entities_final_path(artifact_dir), "w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(included_report_path(artifact_dir), "w", encoding="utf-8") as f:
        for r in deduped:
            report = {
                "wikidata_id": r.get("wikidata_id"),
                "name": r.get("name"),
                "seed_qid": r.get("_seed_qid"),
                "expansion_from": r.get("_expansion_from"),
            }
            f.write(json.dumps(report, ensure_ascii=False) + "\n")

    with open(excluded_report_path(artifact_dir), "w", encoding="utf-8") as f:
        for e in excluded:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    manifest = {
        "run_id": artifact_dir.name,
        "artifact_dir": str(artifact_dir),
        "seed_count": len(seeds),
        "entity_count": len(deduped),
        "excluded_count": len(excluded),
    }
    with open(manifest_path(artifact_dir), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
