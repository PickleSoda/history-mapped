from __future__ import annotations

import re
import time
from typing import Any

import requests
from requests.exceptions import RequestException

from pipeline.agent.log_config import get_logger
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


def search_wikidata_by_name(name: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Wikidata by label via wbsearchentities API.

    Fetches up to `limit` results. Each match contains:
    qid, label, description, aliases, match_type (label/alias).
    Fast REST endpoint (~200ms).
    """
    data = _wikidata_get({
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": str(min(limit, 50)),
    })
    if not data:
        return []

    results = []
    for item in data.get("search", []):
        qid = item.get("id", "")
        if qid:
            match_info = item.get("match", {})
            results.append({
                "qid": qid,
                "label": item.get("label", ""),
                "description": item.get("description", ""),
                "aliases": item.get("aliases", []),
                "match_type": match_info.get("type", ""),
            })
    logger.info("Wikidata search: '%s' → %d results", name, len(results))
    return results


def _rank_candidates(
    candidates: list[dict[str, Any]],
    entity_label: str,
    entity_type: str,
) -> list[dict[str, Any]]:
    """Score and rank Wikidata candidates by relevance.

    Scoring factors (max 1.0):
    - Label exact match (case-insensitive): +0.5
    - Label starts with entity_label: +0.3
    - Entity label is substring of label: +0.2
    - Match type is 'label' (not alias): +0.1
    - Description contains entity_type keywords: +0.2
    - Description mentions ancient/historical: +0.1
    - Penalty for modern places (-0.15) when type is city/place

    Returns candidates sorted by score descending, with 'score' key added.
    """
    name_lower = entity_label.lower()

    # Keywords that indicate the right kind of entity by type
    type_keywords: dict[str, list[str]] = {
        "person": ["king", "queen", "ruler", "emperor", "pharaoh", "conqueror",
                    "general", "commander", "prince", "princess", "noble",
                    "politician", "statesman", "monarch", "macedon", "macedonia",
                    "greek", "persian"],
        "city": ["city", "town", "ancient city", "settlement", "municipality",
                 "capital", "port", "polis", "metropolis"],
        "political_entity": ["empire", "kingdom", "state", "dynasty", "republic",
                             "civilization", "country", "nation", "polity"],
        "event_battle": ["battle", "war", "conflict", "siege", "campaign", "fight"],
        "event_war": ["war", "conflict", "campaign", "military"],
        "military_unit": ["army", "military", "force", "legion", "regiment", "unit"],
        "place": ["region", "area", "land", "territory", "province", "valley",
                  "peninsula", "river", "sea", "ancient"],
    }
    keywords = type_keywords.get(entity_type, [])

    # Penalty keywords that suggest modern/irrelevant matches
    modern_penalties = ["united states", "county", "texas", "mississippi",
                        "town in", "city in", "male given name", "surname",
                        "disambiguation"]

    scored = []
    for c in candidates:
        score = 0.0
        label = c.get("label", "")
        desc = c.get("description", "")
        match_type = c.get("match_type", "")

        # Exact label match — best signal
        if label.lower() == name_lower:
            score += 0.5
        # Label starts with our search term
        elif label.lower().startswith(name_lower):
            score += 0.3
        # Our search term is in the label
        elif name_lower in label.lower():
            score += 0.2
        # Our search term is an alias
        elif any(name_lower == a.lower() for a in c.get("aliases", [])):
            score += 0.15

        # Match type is 'label' (explicit, not alias)
        if match_type == "label":
            score += 0.1

        # Description contains keywords relevant to entity_type
        if desc:
            desc_lower = desc.lower()
            for kw in keywords:
                if kw in desc_lower:
                    score += 0.2
                    break

        # Description mentions ancient/historical
        if desc and any(w in desc_lower for w in ["ancient", "historical", "classical"]):
            score += 0.15

        # Penalty for modern/irrelevant descriptions
        if desc:
            desc_lower = desc.lower()
            for p in modern_penalties:
                if p in desc_lower:
                    score -= 0.15
                    break

        # Bonus: label is single word and matches exactly (for city/place names)
        if entity_type in ("city", "place") and label.lower() == name_lower and not desc:
            score -= 0.1  # No description = too generic

        capped = max(0.0, min(score, 1.0))
        c["score"] = round(capped, 3)
        scored.append(c)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


_WD_YEAR_RE = re.compile(r"^([+-]?\d+)")


def _wikidata_date(value: dict[str, Any]) -> str | None:
    """Return a precision-aware date string from a Wikidata time datavalue.

    Wikidata's ``time`` is always a full timestamp (e.g. "+0750-01-01T00:00:00Z")
    even when only the year is known — the ``-01-01`` is filler driven by the
    ``precision`` field (11=day, 10=month, 9=year, ≤8=decade/coarser). When
    precision is year-or-coarser we drop to year-only ("+0750") so the pipeline
    never persists a fabricated month/day; finer precision keeps the full date.
    """
    time_str = value.get("time")
    if not isinstance(time_str, str) or not time_str:
        return None
    precision = value.get("precision")
    if isinstance(precision, int) and precision <= 9:
        match = _WD_YEAR_RE.match(time_str)
        return match.group(1) if match else time_str
    return time_str


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
                        start_date = _wikidata_date(claims[prop][0]["mainsnak"]["datavalue"]["value"])
                        if start_date:
                            break
                    except (KeyError, IndexError, TypeError):
                        pass

            # End date: try P576 (dissolved) → P570 (death)
            end_date = None
            for prop in ("P576", "P570"):
                if prop in claims:
                    try:
                        end_date = _wikidata_date(claims[prop][0]["mainsnak"]["datavalue"]["value"])
                        if end_date:
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
