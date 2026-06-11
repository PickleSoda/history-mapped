from __future__ import annotations

import time
from typing import Any

import requests
from requests.exceptions import RequestException

from pipeline.agent.logging import get_logger
from pipeline.config import settings

logger = get_logger(__name__)

# Wikidata REST APIs (preferred over SPARQL — faster and not blocked on some networks)
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_API = "https://www.wikidata.org/wiki/Special:EntityData"


def _wikidata_get(params: dict[str, str], timeout: int = 10) -> dict[str, Any] | None:
    """Make a GET request to the Wikidata action API."""
    try:
        t0 = time.time()
        response = requests.get(
            WIKIDATA_API,
            params=params,
            headers={"User-Agent": settings.wikidata_user_agent},
            timeout=timeout,
        )
        response.raise_for_status()
        elapsed = time.time() - t0
        logger.info("Wikidata API OK (%.1fs): %s", elapsed, params.get("action", ""))
        return response.json()
    except RequestException as exc:
        logger.warning("Wikidata API error: %s — %s", params.get("action", ""), exc)
        return None


def search_wikidata_by_name(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search Wikidata by label via wbsearchentities API.

    Each match contains: qid, label, description.
    Fast REST endpoint (~200ms), works when SPARQL is blocked.
    """
    data = _wikidata_get({
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": str(limit),
    })
    if not data:
        return []

    results = []
    for item in data.get("search", []):
        qid = item.get("id", "")
        if qid:
            results.append({
                "qid": qid,
                "label": item.get("label", ""),
                "description": item.get("description", ""),
            })
    logger.info("Wikidata search: '%s' → %d results", name, len(results))
    return results


def enrich_wikidata_entities(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch Wikidata records via the REST EntityData endpoint.

    Fast REST endpoint (~200ms per QID), works when SPARQL is blocked.
    Returns a dict mapping qid → {label, description, coordinates, start_date, end_date}.
    """
    if not qids:
        return {}

    results: dict[str, dict[str, Any]] = {}
    for qid in qids:
        url = f"{WIKIDATA_ENTITY_API}/{qid}.json"
        try:
            t0 = time.time()
            response = requests.get(
                url,
                headers={"User-Agent": settings.wikidata_user_agent},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            entity = data.get("entities", {}).get(qid, {})
            elapsed = time.time() - t0

            labels = entity.get("labels", {})
            descriptions = entity.get("descriptions", {})
            claims = entity.get("claims", {})

            # Extract label
            label = labels.get("en", {}).get("value", "") if labels else ""

            # Extract description
            description = descriptions.get("en", {}).get("value", "") if descriptions else ""

            # Extract coordinates (P625)
            coordinates = None
            if "P625" in claims:
                try:
                    coords = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
                    coordinates = f"Point({coords['longitude']} {coords['latitude']})"
                except (KeyError, IndexError, TypeError):
                    pass

            # Extract inception date (P571)
            start_date = None
            if "P571" in claims:
                try:
                    start_date = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass

            # Extract dissolved date (P576)
            end_date = None
            if "P576" in claims:
                try:
                    end_date = claims["P576"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass

            results[qid] = {
                "label": label,
                "description": description,
                "coordinates": coordinates,
                "start_date": start_date,
                "end_date": end_date,
            }
            logger.info("Wikidata enrich: %s → %s (%.1fs)", qid, label, elapsed)

        except RequestException as exc:
            logger.warning("Wikidata enrich error for %s: %s", qid, exc)

    logger.info("Wikidata enrich: %d/%d resolved", len(results), len(qids))
    return results
