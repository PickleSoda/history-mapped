"""Batch Wikidata enrichment for OHM relation wikidata QIDs."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import orjson
import requests

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_USER_AGENT = "history-mapped-Pipeline/1.0 (https://history-mapped.example)"

_SPARQL_TEMPLATE = """
SELECT ?polity ?polityLabel ?polityDescription
       (GROUP_CONCAT(DISTINCT ?altLabelVal; SEPARATOR=\"||\") AS ?altLabel)
       ?inception ?dissolution
WHERE {{
  VALUES ?polity {{ {qid_list} }}
  OPTIONAL {{ ?polity wdt:P571 ?inception. }}
  OPTIONAL {{ ?polity wdt:P576 ?dissolution. }}
  OPTIONAL {{ ?polity skos:altLabel ?altLabelVal. FILTER(LANG(?altLabelVal)=\"en\") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
}}
GROUP BY ?polity ?polityLabel ?polityDescription ?inception ?dissolution
"""


def _build_sparql_query(qids: list[str]) -> str:
    qid_list = " ".join(f"wd:{qid}" for qid in qids)
    return _SPARQL_TEMPLATE.format(qid_list=qid_list)


def _sparql_query(query: str) -> list[dict[str, Any]]:
    # Lazy import keeps tests lightweight when SPARQLWrapper is not installed.
    from SPARQLWrapper import JSON, SPARQLWrapper

    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]


def _extract_year(iso_val: str | None) -> str | None:
    if not iso_val:
        return None

    match = re.match(r"(-?\d+)", iso_val)
    return match.group(1) if match else None


def batch_enrich_qids(qids: list[str], batch_size: int = 50) -> dict[str, dict[str, Any]]:
    """Return a metadata dict keyed by QID."""
    results: dict[str, dict[str, Any]] = {}
    deduped_qids = list(dict.fromkeys(qids))

    for i in range(0, len(deduped_qids), batch_size):
        batch = deduped_qids[i : i + batch_size]
        try:
            bindings = _sparql_query(_build_sparql_query(batch))
        except Exception as exc:
            logger.warning("SPARQL batch failed for batch starting at %s: %s", i, exc)
            continue

        for row in bindings:
            uri = row.get("polity", {}).get("value", "")
            qid = uri.rsplit("/", 1)[-1]
            aliases_raw = row.get("altLabel", {}).get("value", "")
            aliases = [alias.strip() for alias in aliases_raw.split("||") if alias.strip()] if aliases_raw else []

            results[qid] = {
                "name_en": row.get("polityLabel", {}).get("value"),
                "description": row.get("polityDescription", {}).get("value"),
                "aliases_en": aliases,
                "temporal_start": _extract_year(row.get("inception", {}).get("value")),
                "temporal_end": _extract_year(row.get("dissolution", {}).get("value")),
            }

    return results


def search_qid_by_name(name: str, min_score: float = 0.0, debug: bool = False) -> str | None:
    """Search Wikidata by name and return the best matching QID.
    
    Args:
        name: Entity name to search for
        min_score: Minimum confidence score (0-1) to accept a match. Default 0.0 = accept all.
        debug: If True, log all candidates for audit purposes.
    
    Returns:
        Best matching QID or None if no match found / below threshold.
    """
    search_term = str(name).strip()
    if not search_term:
        return None

    params = {
        "action": "wbsearchentities",
        "search": search_term,
        "language": "en",
        "format": "json",
        "limit": 5,
    }

    try:
        response = requests.get(
            WIKIDATA_API,
            params=params,
            timeout=30,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("Wikidata name search failed for %r: %s", search_term, exc)
        return None

    results = payload.get("search", [])
    if not results:
        logger.debug("No Wikidata results for: %s", search_term)
        return None

    # Log top 3 candidates for visibility
    for i, r in enumerate(results[:3], 1):
        desc = r.get("description", "")
        match = r.get("match", {})
        score = match.get("text", {}).get("confidence", 0) if isinstance(match, dict) else 0
        qid = r.get("id", "")
        if debug or i == 1:
            logger.info(
                "  Candidate %d (score=%.2f): %s — %s (%s)",
                i,
                score,
                qid,
                r.get("label", ""),
                desc,
            )

    # Evaluate top match
    top_match = results[0]
    qid = top_match.get("id")
    
    if not isinstance(qid, str) or not qid:
        return None
    
    # Check score threshold if provided
    match_data = top_match.get("match", {})
    if isinstance(match_data, dict):
        score = match_data.get("text", {}).get("confidence", 0) if isinstance(match_data.get("text"), dict) else 0
        if score < min_score:
            logger.debug(
                "Wikidata match for %r below threshold: %s (score=%.2f < %.2f)",
                search_term,
                qid,
                score,
                min_score,
            )
            return None
    
    logger.info("Resolved %r -> %s", search_term, qid)
    return qid


def _merge_metadata(record: dict[str, Any], metadata: dict[str, Any], match_source: str) -> dict[str, Any]:
    enriched = dict(record)

    if metadata.get("name_en") and not enriched.get("name"):
        enriched["name"] = metadata["name_en"]

    if metadata.get("description") and not enriched.get("summary"):
        enriched["summary"] = metadata["description"]

    aliases = metadata.get("aliases_en") or []
    if aliases and not enriched.get("alternative_names"):
        enriched["alternative_names"] = aliases

    if metadata.get("temporal_start") and not enriched.get("temporal_start"):
        enriched["temporal_start"] = metadata["temporal_start"]

    if metadata.get("temporal_end") and not enriched.get("temporal_end"):
        enriched["temporal_end"] = metadata["temporal_end"]

    enriched["_wikidata_match_source"] = match_source
    return enriched


def enrich_output_jsonl_missing_qids(
    *,
    input_path: str | Path,
    output_path: str | Path,
    batch_size: int = 50,
    searcher: Any = search_qid_by_name,
    enricher: Any = batch_enrich_qids,
) -> dict[str, Any]:
    source_path = Path(input_path)
    destination_path = Path(output_path)

    records: list[dict[str, Any]] = []
    qids_in_order: list[str] = []
    searched_count = 0
    matched_count = 0

    with source_path.open("rb") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue

            record = orjson.loads(raw_line)
            qid = record.get("wikidata_id")

            if isinstance(qid, str) and qid:
                qids_in_order.append(qid)
                record["_wikidata_match_source"] = "existing_qid"
                records.append(record)
                continue

            searched_count += 1
            # Enable debug logging for first 10 searches to audit match quality
            debug = searched_count <= 10
            resolved_qid = searcher(record.get("name", ""), debug=debug)
            if isinstance(resolved_qid, str) and resolved_qid:
                record["wikidata_id"] = resolved_qid
                qids_in_order.append(resolved_qid)
                record["_wikidata_match_source"] = "name_search"
                matched_count += 1
            else:
                record["_wikidata_match_source"] = "name_search_unmatched"

            records.append(record)

    metadata_by_qid = enricher(list(dict.fromkeys(qids_in_order)), batch_size) if qids_in_order else {}

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with destination_path.open("wb") as handle:
        for record in records:
            qid = record.get("wikidata_id")
            if isinstance(qid, str) and qid in metadata_by_qid:
                record = _merge_metadata(record, metadata_by_qid[qid], record.get("_wikidata_match_source", "existing_qid"))

            handle.write(orjson.dumps(record) + b"\n")

    return {
        "record_count": len(records),
        "searched_count": searched_count,
        "matched_count": matched_count,
        "output_path": destination_path,
    }
