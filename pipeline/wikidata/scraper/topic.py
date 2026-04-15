"""Topic-based graph-walk scraper.

Instead of querying "all instances of class X", this module starts from a
single Wikidata item (e.g., Q484954 = Late Bronze Age Collapse) and walks
its linked properties to discover a cluster of related entities across
multiple entity types.

Usage (via CLI):
    python -m pipeline topic "Late Bronze Age Collapse" --depth 2 --limit 200
    python -m pipeline topic Q484954 --depth 2 --limit 200

The walk follows properties like P710 (participant), P276 (location),
P828 (has cause), P1542 (has effect), P527 (has part), P361 (part of),
etc. — essentially any property whose value is another Wikidata entity.
Each discovered entity is classified into one of the 30 WikiGlobe types
by checking its P31 (instance of) against WIKIDATA_TYPE_CONFIGS.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

import requests
from ratelimit import limits, sleep_and_retry

from pipeline.config import settings
from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS, WIKIDATA_REF_CONFIGS
from pipeline.wikidata.scraper.geoshape import GeoshapeResolver

logger = logging.getLogger(__name__)

# ── Properties worth following during the graph walk ─────────────────────────
# These are Wikidata property IDs whose values are other entities (QIDs).
# Organized by how "close" the linked entity is to the seed topic.

WALK_PROPERTIES: list[str] = [
    # Structural / compositional
    "P361",   # part of
    "P527",   # has part / has parts
    "P31",    # instance of (for classification, not walking — see below)

    # Participants & actors
    "P710",   # participant
    "P1344",  # participant of
    "P607",   # conflict (military conflict of a person/unit)
    "P6",     # head of government
    "P35",    # head of state

    # Spatial — location/capital only, NOT country/admin-territory (too broad)
    "P276",   # location
    "P36",    # capital
    "P1376",  # capital of

    # Temporal / successional
    "P155",   # follows (predecessor)
    "P156",   # followed by (successor)

    # Causal
    "P828",   # has cause
    "P1542",  # has effect
    "P1478",  # has immediate cause

    # Cultural / economic
    "P50",    # author
    "P112",   # founded by
    "P84",    # architect
    "P38",    # currency

    # Person-specific
    "P19",    # place of birth
    "P20",    # place of death
    "P22",    # father
    "P25",    # mother
    "P26",    # spouse

    # Significant events
    "P793",   # significant event
]

# Properties to exclude from walking (too broad — lead to modern nation-states
# or unrelated taxonomy nodes; retained for relationship-hint extraction only)
SKIP_WALK_PROPERTIES: set[str] = {
    "P31",    # instance of — used for classification only
    "P279",   # subclass of — taxonomy walk, not topic walk
    "P17",    # country — jumps from any historical region to modern sovereign states
    "P131",   # located in administrative territory — same problem as P17
    "P150",   # contains administrative territory — same problem
}

# ── Modern-state filter ───────────────────────────────────────────────────────
# Wikidata P31 class QIDs that unambiguously identify a modern sovereign state.
# Entities whose P31 contains any of these (and no historical-entity exemption)
# are silently dropped from the BFS output — they are irrelevant to historical
# topic walks and are routinely pulled in as "has part" children of modern
# geographic nodes (Near East, Eastern Mediterranean, etc.).
MODERN_STATE_CLASSES: frozenset[str] = frozenset({
    "Q3624078",  # sovereign state
    "Q1763527",  # constituent country
    "Q6256",     # country (modern sense; exempt if entity also has a historical class)
    "Q7275",     # state (present-day; exempt if entity also has a historical class)
})

# P31 classes that indicate the entity is a *historical* polity rather than a
# present-day state — used to exempt entities that happen to also have Q6256/Q7275.
HISTORICAL_ENTITY_CLASSES: frozenset[str] = frozenset({
    "Q3024240",   # historical country
    "Q28171280",  # ancient civilization
    "Q208281",    # polity (broad historical)
    "Q48349",     # empire
    "Q133442",    # city-state
    "Q28513",     # kingdom
    "Q105543609", # ancient Levantine state
    "Q12097",     # tribal confederation
    "Q8432",      # civilization
})

# ── Reverse mapping: Wikidata class QID → our entity_type ───────────────────
# Built from WIKIDATA_TYPE_CONFIGS at import time for fast lookups.

_CLASS_TO_TYPE: dict[str, str] = {}
for _etype, _config in WIKIDATA_TYPE_CONFIGS.items():
    for _cls in _config.get("wikidata_classes", []):
        # First match wins — more specific types listed first in the dict
        if _cls not in _CLASS_TO_TYPE:
            _CLASS_TO_TYPE[_cls] = _etype

# ── Reverse mapping: Wikidata class QID → reference table category ──────────
# Same idea, but for items that belong to reference tables (eras, regions,
# bodies of water, etc.) rather than regular entities.

_CLASS_TO_REF: dict[str, str] = {}
for _ref_type, _ref_config in WIKIDATA_REF_CONFIGS.items():
    for _cls in _ref_config.get("wikidata_classes", []):
        if _cls not in _CLASS_TO_REF:
            _CLASS_TO_REF[_cls] = _ref_type


class TopicScraper:
    """BFS graph-walk scraper starting from a seed Wikidata QID.

    Discovers related entities across all 30 entity types, up to a
    configurable depth and entity limit.
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_entities: int = 500,
    ):
        self.max_depth = max_depth
        self.max_entities = max_entities
        self.visited: set[str] = set()
        self.collected: list[dict[str, Any]] = []
        self.geoshapes = GeoshapeResolver()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.wikidata_user_agent,
        })

    # ── Public API ───────────────────────────────────────────────────────────

    def resolve_search(self, search_term: str) -> str | None:
        """Resolve a free-text search term to a Wikidata QID.

        Uses the Wikidata wbsearchentities API. Returns the top match QID
        or None if no match found.
        """
        params = {
            "action": "wbsearchentities",
            "search": search_term,
            "language": "en",
            "format": "json",
            "limit": 5,
        }
        try:
            resp = self._api_call("https://www.wikidata.org/w/api.php", params)
            results = resp.get("search", [])
            if not results:
                logger.warning(f"No Wikidata results for: {search_term}")
                return None

            # Log top candidates for the user
            for r in results[:3]:
                desc = r.get("description", "")
                logger.info(f"  Candidate: {r['id']} — {r['label']} ({desc})")

            top = results[0]
            logger.info(f"Resolved '{search_term}' → {top['id']} ({top.get('label', '')})")
            return top["id"]

        except Exception as e:
            logger.error(f"Wikidata search failed: {e}")
            return None

    def walk(self, seed_qid: str, co_seed_qids: list[str] | None = None) -> list[dict[str, Any]]:
        """BFS walk from one or more seed QIDs, collecting related entities.

        ``seed_qid`` is the primary topic.  ``co_seed_qids`` are additional
        starting points inserted at depth 0 alongside the primary seed — useful
        when the primary seed's Wikidata entry is sparse and does not directly
        link to all relevant related entities (e.g. Bronze Age civilisations
        are not reachable from the "Bronze Age Collapse" event item alone).

        Returns a list of raw item dicts (same format as WikidataScraper
        output) that can be passed to EntityMapper.
        """
        self.visited.clear()
        self.collected.clear()

        queue: deque[tuple[str, int]] = deque()  # (qid, depth)
        queue.append((seed_qid, 0))
        self.visited.add(seed_qid)

        # Enqueue co-seeds at depth 0 so they and their neighbours are walked
        # at the same priority as the primary seed.
        for extra_qid in (co_seed_qids or []):
            if extra_qid not in self.visited:
                self.visited.add(extra_qid)
                queue.append((extra_qid, 0))

        while queue and len(self.collected) < self.max_entities:
            qid, depth = queue.popleft()

            # Fetch this entity's data
            entity_data = self._fetch_entity(qid)
            if not entity_data:
                continue

            # Drop modern sovereign states — they flood the output when
            # geographic nodes like "Near East" list countries via P527.
            if self._is_modern_sovereign_state(entity_data):
                logger.debug(f"Skipping modern sovereign state: {qid}")
                continue

            # Classify into one of our 30 types — or a reference table type
            entity_type, ref_type = self._classify(entity_data)

            # Build the raw item dict (matching WikidataScraper output format)
            raw_item = self._build_raw_item(entity_data, entity_type, ref_type)
            if raw_item:
                self.collected.append(raw_item)

            # Walk further if we haven't hit max depth
            if depth < self.max_depth:
                linked_qids = self._extract_linked_qids(entity_data)
                for linked_qid in linked_qids:
                    if linked_qid not in self.visited and len(self.visited) < self.max_entities * 2:
                        self.visited.add(linked_qid)
                        queue.append((linked_qid, depth + 1))

        self._backfill_property_labels()

        logger.info(
            f"Topic walk complete: {len(self.collected)} entities collected, "
            f"{len(self.visited)} QIDs visited"
        )
        return self.collected

    def _backfill_property_labels(self) -> None:
        """Fill empty linked-property labels using labels of already collected items."""
        qid_to_label = {
            item.get("qid"): item.get("label", "")
            for item in self.collected
            if item.get("qid") and item.get("label")
        }

        for item in self.collected:
            properties = item.get("properties", {})
            for entries in properties.values():
                for entry in entries:
                    if entry.get("label"):
                        continue
                    target_qid = entry.get("qid")
                    if target_qid and target_qid in qid_to_label:
                        entry["label"] = qid_to_label[target_qid]

    # ── Wikidata API ─────────────────────────────────────────────────────────

    @sleep_and_retry
    @limits(calls=settings.wikidata_rpm, period=60)
    def _api_call(self, url: str, params: dict) -> dict:
        """Rate-limited API call."""
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_entity(self, qid: str) -> dict | None:
        """Fetch a single entity from the Wikidata API (wbgetentities).

        Returns the entity JSON blob or None on error.
        """
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "languages": "en",
            "props": "labels|descriptions|aliases|claims|sitelinks",
        }
        try:
            data = self._api_call("https://www.wikidata.org/w/api.php", params)
            entities = data.get("entities", {})
            entity = entities.get(qid)
            if not entity or entity.get("missing") is not None:
                return None
            return entity
        except Exception as e:
            logger.error(f"Failed to fetch {qid}: {e}")
            return None

    def _fetch_entities_batch(self, qids: list[str]) -> dict[str, dict]:
        """Fetch up to 50 entities in one API call."""
        results: dict[str, dict] = {}
        # Wikidata allows 50 IDs per request
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
                data = self._api_call("https://www.wikidata.org/w/api.php", params)
                for qid, entity in data.get("entities", {}).items():
                    if entity.get("missing") is None:
                        results[qid] = entity
            except Exception as e:
                logger.error(f"Batch fetch failed for chunk starting at {i}: {e}")
        return results

    # ── Classification ───────────────────────────────────────────────────────

    def _is_modern_sovereign_state(self, entity_data: dict) -> bool:
        """Return True if the entity is a modern sovereign state.

        Checks P31 (instance of) against MODERN_STATE_CLASSES.  Entities that
        match are filtered out of the BFS result set because geographic nodes
        like "Near East" link to them via P527 (has part) and would otherwise
        flood a historical topic walk with present-day countries.

        Exemption: if the entity *also* carries a historical-entity class
        (e.g. Q3024240 historical country, Q28171280 ancient civilization)
        it is kept — ancient Egypt, Hittite Empire, etc. may use Q6256/Q7275
        alongside a more specific historical class.
        """
        claims = entity_data.get("claims", {})
        p31_qids: set[str] = set()
        for claim in claims.get("P31", []):
            val = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(val, dict) and "id" in val:
                p31_qids.add(val["id"])

        # Not a modern state at all — keep it
        if not p31_qids & MODERN_STATE_CLASSES:
            return False

        # Modern state class present — but exempt if a historical class is also present
        if p31_qids & HISTORICAL_ENTITY_CLASSES:
            return False

        return True

    def _classify(self, entity_data: dict) -> tuple[str | None, str | None]:
        """Determine which of our 30 entity_types this Wikidata item maps to.

        Checks P31 (instance of) and walks P279 (subclass of) up to 3 levels
        to find a match in WIKIDATA_TYPE_CONFIGS.

        Returns (entity_type, ref_type) tuple:
        - (entity_type, None) for regular entities
        - (None, ref_type)    for reference-table items (eras, regions, etc.)
        - (None, None)        if truly unclassifiable
        """
        claims = entity_data.get("claims", {})

        # Collect all P31 values (instance of)
        instance_of_qids: list[str] = []
        for claim in claims.get("P31", []):
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if isinstance(value, dict) and "id" in value:
                instance_of_qids.append(value["id"])

        # Direct match: check if any P31 class is in our entity mapping
        for cls_qid in instance_of_qids:
            if cls_qid in _CLASS_TO_TYPE:
                return (_CLASS_TO_TYPE[cls_qid], None)

        # Walk P279 (subclass of) up to 3 levels for entity types
        for cls_qid in instance_of_qids:
            resolved = self._walk_subclass(cls_qid, max_depth=3)
            if resolved:
                return (resolved, None)

        # No entity type match — check reference tables
        for cls_qid in instance_of_qids:
            if cls_qid in _CLASS_TO_REF:
                return (None, _CLASS_TO_REF[cls_qid])

        # Walk P279 for ref table types too
        for cls_qid in instance_of_qids:
            resolved_ref = self._walk_subclass_ref(cls_qid, max_depth=3)
            if resolved_ref:
                return (None, resolved_ref)

        return (None, None)

    def _walk_subclass(self, class_qid: str, max_depth: int = 3) -> str | None:
        """Walk P279 (subclass of) from a class QID to find a known type."""
        visited = {class_qid}
        frontier = [class_qid]

        for _ in range(max_depth):
            next_frontier = []
            for qid in frontier:
                # Fetch parent classes via SPARQL (faster for this specific lookup)
                parents = self._get_parent_classes(qid)
                for parent in parents:
                    if parent in _CLASS_TO_TYPE:
                        return _CLASS_TO_TYPE[parent]
                    if parent not in visited:
                        visited.add(parent)
                        next_frontier.append(parent)
            frontier = next_frontier
            if not frontier:
                break

        return None

    def _walk_subclass_ref(self, class_qid: str, max_depth: int = 3) -> str | None:
        """Walk P279 (subclass of) from a class QID to find a reference table type."""
        visited = {class_qid}
        frontier = [class_qid]

        for _ in range(max_depth):
            next_frontier = []
            for qid in frontier:
                parents = self._get_parent_classes(qid)
                for parent in parents:
                    if parent in _CLASS_TO_REF:
                        return _CLASS_TO_REF[parent]
                    if parent not in visited:
                        visited.add(parent)
                        next_frontier.append(parent)
            frontier = next_frontier
            if not frontier:
                break

        return None

    _parent_class_cache: dict[str, list[str]] = {}

    def _get_parent_classes(self, class_qid: str) -> list[str]:
        """Get direct P279 (subclass of) parents for a class QID."""
        if class_qid in self._parent_class_cache:
            return self._parent_class_cache[class_qid]

        params = {
            "action": "wbgetentities",
            "ids": class_qid,
            "format": "json",
            "props": "claims",
        }
        try:
            data = self._api_call("https://www.wikidata.org/w/api.php", params)
            entity = data.get("entities", {}).get(class_qid, {})
            parents = []
            for claim in entity.get("claims", {}).get("P279", []):
                val = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                if isinstance(val, dict) and "id" in val:
                    parents.append(val["id"])
            self._parent_class_cache[class_qid] = parents
            return parents
        except Exception:
            return []

    # ── Link Extraction ──────────────────────────────────────────────────────

    def _extract_linked_qids(self, entity_data: dict) -> list[str]:
        """Extract QIDs from entity claims that are worth following.

        Only follows properties in WALK_PROPERTIES (minus SKIP_WALK_PROPERTIES).
        Skips values that are strings, quantities, coordinates, etc. — only
        follows wikibase-entityid values (i.e., links to other Q-items).
        """
        claims = entity_data.get("claims", {})
        linked: list[str] = []

        for prop_id in WALK_PROPERTIES:
            if prop_id in SKIP_WALK_PROPERTIES:
                continue
            for claim in claims.get(prop_id, []):
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") != "wikibase-entityid":
                    continue
                value = datavalue.get("value", {})
                target_qid = value.get("id")
                if target_qid and target_qid.startswith("Q"):
                    linked.append(target_qid)

        return linked

    # ── Item Building ────────────────────────────────────────────────────────

    def _build_raw_item(self, entity_data: dict, entity_type: str | None, ref_type: str | None = None) -> dict | None:
        """Convert a Wikidata entity JSON blob into the raw item format
        expected by EntityMapper.

        Returns None if the entity has no English label or is unclassifiable.
        The returned dict matches WikidataScraper's output format:
        {
            qid, label, description, aliases, coords, inception,
            dissolution, wikipedia_title, properties,
            _entity_type, _ref_type
        }
        """
        qid = entity_data.get("id", "")

        # Extract English label
        label = (
            entity_data
            .get("labels", {})
            .get("en", {})
            .get("value", "")
        )
        if not label:
            return None

        # Description
        description = (
            entity_data
            .get("descriptions", {})
            .get("en", {})
            .get("value", "")
        )

        # Aliases
        aliases = [
            a.get("value", "")
            for a in entity_data.get("aliases", {}).get("en", [])
        ]

        # Wikipedia sitelink
        wikipedia_title = (
            entity_data
            .get("sitelinks", {})
            .get("enwiki", {})
            .get("title")
        )

        claims = entity_data.get("claims", {})

        # Coordinates (P625)
        coords = self._extract_coords(claims)

        # Temporal: inception (P571/P580) and dissolution (P576/P582)
        inception = self._extract_time(claims, "P571") or self._extract_time(claims, "P580")
        dissolution = self._extract_time(claims, "P576") or self._extract_time(claims, "P582")

        geoshape = self._extract_geoshape(claims)
        territory_geojson = self.geoshapes.resolve_geometry(geoshape)

        # Properties dict for relationship extraction
        properties = self._extract_properties(claims)

        return {
            "qid": qid,
            "label": label,
            "description": description,
            "aliases": aliases,
            "coords": coords,
            "inception": inception,
            "dissolution": dissolution,
            "geoshape": geoshape,
            "territory_geojson": territory_geojson,
            "wikipedia_title": wikipedia_title,
            "properties": properties,
            # Injected metadata for the mapper — not a Wikidata field
            "_entity_type": entity_type,
            "_ref_type": ref_type,
        }

    def _extract_coords(self, claims: dict) -> dict | None:
        """Extract coordinates from P625 claims."""
        for claim in claims.get("P625", []):
            val = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if "latitude" in val and "longitude" in val:
                return {"lat": val["latitude"], "lon": val["longitude"]}
        return None

    def _extract_time(self, claims: dict, prop: str) -> str | None:
        """Extract a year string from a time-valued property."""
        for claim in claims.get(prop, []):
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") != "time":
                continue
            time_val = datavalue.get("value", {}).get("time", "")
            # Format: "+1200-01-01T00:00:00Z" or "-1200-01-01T00:00:00Z"
            try:
                if time_val.startswith("+"):
                    year_str = time_val[1:].split("-")[0]
                elif time_val.startswith("-"):
                    year_str = "-" + time_val[1:].split("-")[0]
                else:
                    year_str = time_val.split("-")[0]
                year = int(year_str)
                return str(year)
            except (ValueError, IndexError):
                continue
        return None

    def _extract_properties(self, claims: dict) -> dict[str, list[dict]]:
        """Extract entity-link properties for relationship hint generation.

        Only includes properties that link to other entities (wikibase-entityid).
        Returns format matching WikidataScraper._enrich_properties output.
        """
        properties: dict[str, list[dict]] = {}

        # All properties that have entity-link values
        for prop_id, claim_list in claims.items():
            entries = []
            for claim in claim_list:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") != "wikibase-entityid":
                    continue
                value = datavalue.get("value", {})
                target_qid = value.get("id")
                if target_qid:
                    entries.append({
                        "qid": target_qid,
                        "label": "",  # Labels filled by batch later or at import
                        "uri": f"http://www.wikidata.org/entity/{target_qid}",
                    })
            if entries:
                properties[prop_id] = entries

        return properties

    def _extract_geoshape(self, claims: dict) -> str | None:
        """Extract a Commons Data:*.map title from P3896 claims."""
        for claim in claims.get("P3896", []):
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") != "string":
                continue
            value = datavalue.get("value")
            if isinstance(value, str) and value.startswith("Data:") and value.endswith(".map"):
                return value
        return None
