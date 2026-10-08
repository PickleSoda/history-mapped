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


_THROTTLE_STATUSES = {429, 503}
_THROTTLE_RETRIES = 3


def _get_honoring_retry_after(url: str, params: dict[str, str] | None, timeout: int) -> requests.Response:
    """GET that backs off on 429/503 (Retry-After, default 5s) so parallel ingests slow
    down instead of silently dropping resolutions."""
    for attempt in range(_THROTTLE_RETRIES + 1):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": settings.wikidata_user_agent},
            timeout=timeout,
        )
        if response.status_code not in _THROTTLE_STATUSES or attempt == _THROTTLE_RETRIES:
            return response
        try:
            wait = min(float(response.headers.get("Retry-After", 5)), 60.0)
        except ValueError:
            wait = 5.0
        logger.warning("Wikidata throttled (%d); retrying in %.0fs", response.status_code, wait)
        time.sleep(wait)
    return response


def _wikidata_get(params: dict[str, str], timeout: int = 10) -> dict[str, Any] | None:
    """Make a GET request to the Wikidata action API."""
    try:
        t0 = time.time()
        response = _get_honoring_retry_after(WIKIDATA_API, params, timeout)
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
                # The label/alias (any language) the search actually matched —
                # lets the name guard tell an exact hit from a prefix hit.
                "match_text": match_info.get("text", ""),
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


START_DATE_PROPS = ("P571", "P569", "P585")   # inception → birth → point in time
END_DATE_PROPS = ("P576", "P570")             # dissolved → death

# Wikidata time precision: 6 millennium, 7 century, 8 decade, 9 year, 10 month, 11 day.
# A century value is stored as one year of it ("1st century BCE" = -0100, "7th
# century" = +0601 or +0700), so read as a year it is off by up to 99 years.
CENTURY_PRECISION = 7
DECADE_PRECISION = 8


def _claim_time(statements: Any) -> dict[str, Any] | None:
    """The time value to read from a property's statements: a preferred-rank one
    first, else the first normal one; deprecated statements never (they are the
    values Wikidata editors marked wrong, e.g. a superseded birth year)."""
    if not isinstance(statements, list):
        return None
    usable = [s for s in statements if isinstance(s, dict) and s.get("rank") != "deprecated"]
    preferred = [s for s in usable if s.get("rank") == "preferred"]
    for statement in preferred + usable:
        try:
            value = statement["mainsnak"]["datavalue"]["value"]
        except (KeyError, TypeError):
            continue
        if isinstance(value, dict) and value.get("time"):
            return value
    return None


def _first_claim_date(claims: dict[str, Any], props: tuple[str, ...]) -> tuple[str | None, int | None]:
    """(date, precision) of the first of `props` that has a usable time value."""
    for prop in props:
        value = _claim_time(claims.get(prop))
        if value is None:
            continue
        date = _wikidata_date(value)
        if date:
            precision = value.get("precision")
            return date, precision if isinstance(precision, int) else None
    return None, None


def _claim_dates(claims: dict[str, Any]) -> dict[str, Any]:
    """start/end dates of a claims dict plus their Wikidata precision."""
    start_date, start_precision = _first_claim_date(claims, START_DATE_PROPS)
    end_date, end_precision = _first_claim_date(claims, END_DATE_PROPS)
    return {"start_date": start_date, "end_date": end_date,
            "start_precision": start_precision, "end_precision": end_precision}


def _parse_claim_dates(claims: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract (start_date, end_date) from a claims dict, mirroring enrich order:
    start = P571 → P569 → P585; end = P576 → P570."""
    dates = _claim_dates(claims)
    return dates["start_date"], dates["end_date"]


def min_storable_precision(entity_type: str | None) -> int:
    """Coarsest Wikidata precision whose year may be stored as the entity's date.

    A person's birth/death of "1st century BCE" is not a year: stored as -100 it
    gave Coponius -100..100 (200 years). Decades are close enough (≤ 9 years off).
    For polities, cities and other long-lived types a century still places the
    entity on the map; a millennium (+0001 = "1st millennium") does not.
    """
    return DECADE_PRECISION if entity_type == "person" else CENTURY_PRECISION


def storable_wikidata_dates(record: dict[str, Any] | None,
                            entity_type: str | None) -> tuple[str | None, str | None]:
    """(start, end) from a Wikidata record that may be written as the entity's dates.

    Drops a bound coarser than min_storable_precision (an unknown precision, from
    an older cached record, is kept) and, for a person, both bounds when the
    record's own lifespan is impossible (over 110 years, or a sign split: Shuttarna
    II's death is entered as +1375 against a -1350 birth). Disambiguation keeps
    using the raw start_date/end_date, where a century is still era evidence.
    """
    from pipeline.agent.date_utils import MAX_PERSON_LIFESPAN, lifespan_problem
    from pipeline.agent.tools.disambiguation import era_year

    if not record:
        return None, None
    floor = min_storable_precision(entity_type)
    out: list[str | None] = []
    for key in ("start", "end"):
        date = record.get(f"{key}_date")
        precision = record.get(f"{key}_precision")
        out.append(date if date and (not isinstance(precision, int) or precision >= floor) else None)
    start, end = out
    if entity_type == "person":
        # Read each raw bound as the interval its precision allows ("-0100" at
        # century precision = 1st century BCE); if even the closest points give
        # an impossible life, the record itself is wrong (an unsigned BCE year:
        # Shuttarna II "14th century BCE" .. +1375).
        s, e = era_year(record.get("start_date")), era_year(record.get("end_date"))
        if s is not None and e is not None:
            s_slack = _PRECISION_SLACK.get(record.get("start_precision"), 0)
            e_slack = _PRECISION_SLACK.get(record.get("end_precision"), 0)
            if s - s_slack > e + e_slack or (e - e_slack) - (s + s_slack) > MAX_PERSON_LIFESPAN:
                return None, None
    if lifespan_problem(entity_type, era_year(start), era_year(end)):
        return None, None
    return start, end


# Years a coarse Wikidata value may be off by, per precision (millennium, century, decade).
_PRECISION_SLACK = {6: 1000, 7: 100, 8: 10}


def _parse_geo(claims: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract (coordinates_wkt, location_qid) from a claims dict — direct P625
    coordinate, else the QID of an associated place (birth/death/work/location)."""
    coordinates = None
    if "P625" in claims:
        try:
            coords = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
            coordinates = f"Point({coords['longitude']} {coords['latitude']})"
        except (KeyError, IndexError, TypeError):
            pass
    location_qid = None
    if not coordinates:
        for prop in ("P19", "P20", "P937", "P276", "P159", "P131", "P495"):
            if prop in claims:
                try:
                    location_qid = claims[prop][0]["mainsnak"]["datavalue"]["value"]["id"]
                    if location_qid:
                        break
                except (KeyError, IndexError, TypeError):
                    pass
    return coordinates, location_qid


def _en_aliases(entity: dict[str, Any]) -> list[str]:
    """English aliases of a Wikidata entity JSON (wbgetentities / EntityData)."""
    aliases = (entity.get("aliases", {}) or {}).get("en", []) or []
    return [a.get("value", "") for a in aliases if isinstance(a, dict) and a.get("value")]


def fetch_entity_meta(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Batched fetch of disambiguation/verification metadata via wbgetentities.

    One API call per 50 QIDs (vs enrich's one-call-per-QID), returning for each:
    ``p31`` (instance-of QIDs), ``sitelinks`` (count — a popularity prior),
    ``start_date``/``end_date``, ``coordinates``, ``location_qid``, ``label``,
    ``aliases`` (English), ``description``. Used both to re-rank search candidates by type (resolve
    node) and to verify/repair already-committed QIDs (repair pass).
    """
    if not qids:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = _wikidata_get({
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "claims|sitelinks|labels|descriptions|aliases",
            "languages": "en",
            "format": "json",
        })
        if not data:
            continue
        for qid, ent in (data.get("entities", {}) or {}).items():
            if "missing" in ent:
                continue
            claims = ent.get("claims", {}) or {}
            p31 = []
            for c in claims.get("P31", []):
                try:
                    p31.append(c["mainsnak"]["datavalue"]["value"]["id"])
                except (KeyError, IndexError, TypeError):
                    pass
            dates = _claim_dates(claims)
            coordinates, location_qid = _parse_geo(claims)
            labels = ent.get("labels", {}) or {}
            descriptions = ent.get("descriptions", {}) or {}
            out[qid] = {
                "label": labels.get("en", {}).get("value", ""),
                "aliases": _en_aliases(ent),
                "description": descriptions.get("en", {}).get("value", ""),
                "p31": p31,
                "sitelinks": len(ent.get("sitelinks", {}) or {}),
                **dates,
                "coordinates": coordinates,
                "location_qid": location_qid,
            }
    logger.info("Wikidata meta: %d/%d resolved (batched)", len(out), len(qids))
    return out


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
            response = _get_honoring_retry_after(url, None, 10)
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

            # Place of association — for entities that have no coordinate of their
            # own (people, works, religions), the referenced place's coordinate
            # lets them still get a map point. Order: birth → death → work
            # location → location → headquarters → admin territory → origin.
            location_qid = None
            if not coordinates:
                for prop in ("P19", "P20", "P937", "P276", "P159", "P131", "P495"):
                    if prop in claims:
                        try:
                            location_qid = claims[prop][0]["mainsnak"]["datavalue"]["value"]["id"]
                            if location_qid:
                                break
                        except (KeyError, IndexError, TypeError):
                            pass

            # Start: P571 (inception) → P569 (birth) → P585 (point in time);
            # end: P576 (dissolved) → P570 (death). Rank-aware, with precision.
            results[qid] = {
                "label": label,
                "aliases": _en_aliases(entity),
                "description": description,
                "coordinates": coordinates,
                "location_qid": location_qid,
                **_claim_dates(claims),
            }
            logger.info("Wikidata enrich: %s → %s (%.1fs)", qid, label, elapsed)

        except RequestException as exc:
            logger.warning("Wikidata enrich error for %s: %s", qid, exc)

    logger.info("Wikidata enrich: %d/%d resolved", len(results), len(qids))
    return results
