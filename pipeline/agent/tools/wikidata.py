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
    """Fetch Wikidata records via the REST EntityData endpoint (batch).

    Fetches all QIDs in a single request. ~200ms total regardless of QID count.
    Returns a dict mapping qid → {label, description, coordinates, start_date, end_date}.
    """
    if not qids:
        return {}

    qid_list = ",".join(qids)
    url = f"{WIKIDATA_ENTITY_API}/{qid_list}.json"
    try:
        t0 = time.time()
        response = requests.get(
            url,
            headers={"User-Agent": settings.wikidata_user_agent},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        entities = data.get("entities", {})
        elapsed = time.time() - t0

        results: dict[str, dict[str, Any]] = {}
        for qid, entity in entities.items():
            if qid == '-1':
                continue
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

            # Inception date (P571) — for polities, events, organizations
            start_date = None
            if "P571" in claims:
                try:
                    start_date = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass
            # Date of birth (P569) — for persons
            if not start_date and "P569" in claims:
                try:
                    start_date = claims["P569"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass
            # Point in time (P585) — for events
            if not start_date and "P585" in claims:
                try:
                    start_date = claims["P585"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass

            # Dissolved date (P576) — for polities, organizations
            end_date = None
            if "P576" in claims:
                try:
                    end_date = claims["P576"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass
            # Date of death (P570) — for persons
            if not end_date and "P570" in claims:
                try:
                    end_date = claims["P570"][0]["mainsnak"]["datavalue"]["value"]["time"]
                except (KeyError, IndexError, TypeError):
                    pass

            results[qid] = {
                "label": label,
                "description": description,
                "coordinates": coordinates,
                "start_date": start_date,
                "end_date": end_date,
            }

        logger.info("Wikidata enrich: %d/%d resolved (%.1fs)", len(results), len(qids), elapsed)
        return results

    except RequestException as exc:
        logger.warning("Wikidata enrich batch error for %s: %s", qid_list, exc)
        return {}
