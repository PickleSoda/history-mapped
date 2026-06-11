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

    Fetches each QID individually (~200ms each). Top-priority properties:
    P571 (inception), P569 (date of birth), P585 (point in time) for start_date,
    P576 (dissolved), P570 (date of death) for end_date, P625 (coordinate location).
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
            entity = response.json().get("entities", {}).get(qid, {})
            elapsed = time.time() - t0

            labels = entity.get("labels", {})
            descriptions = entity.get("descriptions", {})
            claims = entity.get("claims", {})

            label = labels.get("en", {}).get("value", "") if labels else ""
            description = descriptions.get("en", {}).get("value", "") if descriptions else ""

            # Coordinates (P625)
            coordinates = None
            if "P625" in claims:
                try:
                    coords = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
                    coordinates = f"Point({coords['longitude']} {coords['latitude']})"
                except (KeyError, IndexError, TypeError):
                    pass

            # Start date: try P571 (inception) → P569 (birth) → P585 (point in time)
            start_date = None
            for prop in ("P571", "P569", "P585"):
                if prop in claims:
                    try:
                        start_date = claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"]
                        break
                    except (KeyError, IndexError, TypeError):
                        pass

            # End date: try P576 (dissolved) → P570 (death)
            end_date = None
            for prop in ("P576", "P570"):
                if prop in claims:
                    try:
                        end_date = claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"]
                        break
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
