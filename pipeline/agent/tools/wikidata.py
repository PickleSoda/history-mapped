from __future__ import annotations

import time
from typing import Any

import requests
from requests.exceptions import RequestException

from pipeline.agent.logging import get_logger
from pipeline.config import settings

logger = get_logger(__name__)


def _query_sparql(query: str, max_retries: int = 2) -> dict[str, Any]:
    """Run a SPARQL query against Wikidata with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            t0 = time.time()
            response = requests.get(
                settings.wikidata_endpoint,
                params={"query": query, "format": "json"},
                headers={"User-Agent": settings.wikidata_user_agent},
                timeout=30,
            )
            response.raise_for_status()
            elapsed = time.time() - t0
            logger.info("Wikidata SPARQL OK (%.1fs)", elapsed)
            return response.json()
        except RequestException as exc:
            elapsed = time.time() - t0 if 't0' in locals() else 0.0
            if attempt < max_retries:
                logger.warning("Wikidata SPARQL attempt %d/%d failed (%.1fs): %s — retrying",
                               attempt + 1, max_retries + 1, elapsed, exc)
                time.sleep(2 ** attempt)
                continue
            logger.warning("Wikidata SPARQL FAILED after %d attempts (%.1fs): %s",
                           max_retries + 1, elapsed, exc)
            return {"results": {"bindings": []}}


def search_wikidata_by_name(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search Wikidata by label, return candidate matches.

    Each match contains: qid, label, description.
    """
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription WHERE {{
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      ?item rdfs:label ?itemLabel.
      FILTER(CONTAINS(LCASE(?itemLabel), LCASE("{name}")))
    }}
    LIMIT {limit}
    """
    data = _query_sparql(query)
    results = []
    for binding in data.get("results", {}).get("bindings", []):
        item_url = binding.get("item", {}).get("value", "")
        qid = item_url.split("/")[-1] if "/entity/" in item_url else ""
        results.append({
            "qid": qid,
            "label": binding.get("itemLabel", {}).get("value", ""),
            "description": binding.get("itemDescription", {}).get("value", ""),
        })
    return results


def enrich_wikidata_entities(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch basic Wikidata records for a list of QIDs.

    Returns a dict mapping qid → {label, description, aliases, coordinates, start_date, end_date}.
    """
    if not qids:
        return {}

    qid_values = " ".join(f"wd:{q}" for q in qids)
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?coord ?inception ?dissolved WHERE {{
      VALUES ?item {{ {qid_values} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      OPTIONAL {{ ?item wdt:P625 ?coord. }}
      OPTIONAL {{ ?item wdt:P571 ?inception. }}
      OPTIONAL {{ ?item wdt:P576 ?dissolved. }}
    }}
    """
    data = _query_sparql(query)
    results = {}
    for binding in data.get("results", {}).get("bindings", []):
        item_url = binding.get("item", {}).get("value", "")
        qid = item_url.split("/")[-1] if "/entity/" in item_url else ""
        if qid:
            results[qid] = {
                "label": binding.get("itemLabel", {}).get("value", ""),
                "description": binding.get("itemDescription", {}).get("value", ""),
                "coordinates": binding.get("coord", {}).get("value"),
                "start_date": binding.get("inception", {}).get("value"),
                "end_date": binding.get("dissolved", {}).get("value"),
            }
    return results
