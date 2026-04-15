"""Wikidata SPARQL scraper.

Queries Wikidata for historical entities, returns structured dicts with
QIDs, labels, coordinates, temporal data, and Wikidata property links
(used later for relationship extraction).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from SPARQLWrapper import SPARQLWrapper, JSON
from ratelimit import limits, sleep_and_retry

from pipeline.config import settings
from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS
from pipeline.wikidata.scraper.geoshape import GeoshapeResolver

logger = logging.getLogger(__name__)

BASE_PROPERTY_QUERIES: list[str] = [
    "P3896", # geoshape
    "P17",   # country
    "P131",  # located in admin territory
    "P276",  # location
    "P36",   # capital
    "P1376", # capital of
    "P361",  # part of
    "P527",  # has part
    "P155",  # follows
    "P156",  # followed by
]


class WikidataScraper:
    """Fetch structured entity data from Wikidata via SPARQL."""

    def __init__(self):
        self.sparql = SPARQLWrapper(settings.wikidata_endpoint)
        self.sparql.setReturnFormat(JSON)
        self.sparql.addCustomHttpHeader("User-Agent", settings.wikidata_user_agent)
        self.geoshapes = GeoshapeResolver()

    @sleep_and_retry
    @limits(calls=settings.wikidata_rpm, period=60)
    def _execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a SPARQL query with rate limiting."""
        self.sparql.setQuery(query)
        try:
            results = self.sparql.query().convert()
            return results["results"]["bindings"]
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            return []

    def query_entities(
        self,
        entity_type: str,
        limit: int = 100,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query Wikidata for entities of the given type.

        Returns a list of dicts with raw Wikidata fields:
        - qid: Wikidata QID (e.g. "Q2736")
        - label: primary label
        - description: Wikidata description
        - aliases: list of alternative names
        - coords: {lat, lon} if available
        - inception: inception year
        - dissolution: dissolution year
        - start_time: start year (P580)
        - end_time: end year (P582)
        - point_in_time: point year (P585)
        - location_name: best location label (P276/P131/P17)
        - wikipedia_title: English Wikipedia article title
        - properties: dict of Wikidata property values for relationship extraction
        """
        config = WIKIDATA_TYPE_CONFIGS.get(entity_type)
        if not config:
            logger.warning(f"No Wikidata config for entity_type={entity_type}")
            return []

        # Build SPARQL query from type config
        query = self._build_query(config, limit, start_year, end_year)
        logger.info(f"Querying Wikidata for {entity_type} (limit={limit})")

        raw_bindings = self._execute_query(query)
        if not raw_bindings:
            return []

        # Parse bindings into structured dicts
        items = []
        for binding in raw_bindings:
            item = self._parse_binding(binding, config)
            if item:
                items.append(item)

        # Fetch additional properties (relationships, locations, geoshapes) in batches
        if items:
            items = self._enrich_properties(items, config)

        items = self._enrich_geoshapes(items)

        return items

    def _build_query(
        self,
        config: dict,
        limit: int,
        start_year: int | None,
        end_year: int | None,
    ) -> str:
        """Build a SPARQL query from a type config."""
        # Base: instance_of or subclass_of the Wikidata class
        wikidata_classes = config["wikidata_classes"]
        class_filter = " ".join(f"wd:{cls}" for cls in wikidata_classes)

        # Optional temporal filter
        temporal_filter = ""
        if start_year is not None or end_year is not None:
            temporal_filter = "OPTIONAL { ?item wdt:P571 ?inception . }\n"
            temporal_filter += "OPTIONAL { ?item wdt:P576 ?dissolution . }\n"
            conditions = []
            if start_year is not None:
                conditions.append(
                    f'(!BOUND(?dissolution) || YEAR(?dissolution) >= {start_year})'
                )
            if end_year is not None:
                conditions.append(
                    f'(!BOUND(?inception) || YEAR(?inception) <= {end_year})'
                )
            temporal_filter += "FILTER(" + " && ".join(conditions) + ")\n"

        # Build the query
        query = f"""
         SELECT DISTINCT ?item ?itemLabel ?itemDescription ?coord
             ?inception ?dissolution ?start_time ?end_time ?point_in_time
             ?locationLabel ?adminLabel ?countryLabel
             ?wikipedia_title
        WHERE {{
          ?item wdt:P31/wdt:P279* ?class .
          VALUES ?class {{ {class_filter} }}

          {temporal_filter}

          OPTIONAL {{ ?item wdt:P625 ?coord . }}
          {'OPTIONAL { ?item wdt:P571 ?inception . }' if not temporal_filter else ''}
          {'OPTIONAL { ?item wdt:P576 ?dissolution . }' if not temporal_filter else ''}
          OPTIONAL {{ ?item wdt:P580 ?start_time . }}
          OPTIONAL {{ ?item wdt:P582 ?end_time . }}
          OPTIONAL {{ ?item wdt:P585 ?point_in_time . }}
          OPTIONAL {{ ?item wdt:P276 ?location . }}
          OPTIONAL {{ ?item wdt:P131 ?admin . }}
          OPTIONAL {{ ?item wdt:P17 ?country . }}

          OPTIONAL {{
            ?wikipedia_article schema:about ?item ;
                               schema:isPartOf <https://{settings.wikipedia_language}.wikipedia.org/> ;
                               schema:name ?wikipedia_title .
          }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{settings.wikipedia_language},en" . }}
        }}
        LIMIT {limit}
        """
        return query

    def _parse_binding(self, binding: dict, config: dict) -> dict[str, Any] | None:
        """Parse a SPARQL result binding into a structured dict."""
        qid_uri = binding.get("item", {}).get("value", "")
        if not qid_uri:
            return None

        qid = qid_uri.split("/")[-1]  # e.g., "Q2736"
        label = binding.get("itemLabel", {}).get("value", "")
        description = binding.get("itemDescription", {}).get("value", "")

        # Skip items where label == QID (no localized label available)
        if label == qid:
            return None

        # Parse coordinates
        coords = None
        coord_val = binding.get("coord", {}).get("value", "")
        if coord_val and coord_val.startswith("Point("):
            # Format: "Point(lon lat)"
            parts = coord_val.replace("Point(", "").replace(")", "").split()
            if len(parts) == 2:
                coords = {"lon": float(parts[0]), "lat": float(parts[1])}

        # Parse dates
        inception = self._parse_date(binding.get("inception", {}).get("value"))
        dissolution = self._parse_date(binding.get("dissolution", {}).get("value"))
        start_time = self._parse_date(binding.get("start_time", {}).get("value"))
        end_time = self._parse_date(binding.get("end_time", {}).get("value"))
        point_in_time = self._parse_date(binding.get("point_in_time", {}).get("value"))

        location_name = (
            binding.get("locationLabel", {}).get("value")
            or binding.get("adminLabel", {}).get("value")
            or binding.get("countryLabel", {}).get("value")
            or None
        )

        return {
            "qid": qid,
            "label": label,
            "description": description,
            "aliases": [],  # filled by a separate aliases query or Wikipedia
            "coords": coords,
            "inception": inception,
            "dissolution": dissolution,
            "start_time": start_time,
            "end_time": end_time,
            "point_in_time": point_in_time,
            "location_name": location_name,
            "wikipedia_title": binding.get("wikipedia_title", {}).get("value"),
            "properties": {},
        }

    def _parse_date(self, date_str: str | None) -> str | None:
        """Parse an xsd:dateTime into a year string (negative for BCE)."""
        if not date_str:
            return None
        try:
            # Format: "±YYYY-MM-DDT00:00:00Z" or "YYYY-MM-DDT00:00:00Z"
            year_part = date_str.split("-")[0] if not date_str.startswith("-") else "-" + date_str[1:].split("-")[0]
            year = int(year_part)
            return str(year)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_point_wkt(point_wkt: str | None) -> dict[str, float] | None:
        """Parse a WKT Point string into a {lon, lat} dict."""
        if not point_wkt or not point_wkt.startswith("Point("):
            return None

        parts = point_wkt.replace("Point(", "").replace(")", "").split()
        if len(parts) != 2:
            return None

        try:
            return {"lon": float(parts[0]), "lat": float(parts[1])}
        except ValueError:
            return None

    def _enrich_properties(
        self, items: list[dict], config: dict
    ) -> list[dict]:
        """Batch-fetch additional Wikidata properties for relationship extraction.

        For each item, queries properties like P17 (country), P131 (admin territory),
        P36 (capital), P1376 (capital of), etc., which map to our 76 relationship types.
        """
        qids = [item["qid"] for item in items]

        property_ids = list(dict.fromkeys(config.get("property_queries", []) + BASE_PROPERTY_QUERIES))
        if not property_ids:
            return items

        chunk_size = 50
        qid_to_item = {item["qid"]: item for item in items}

        for i in range(0, len(qids), chunk_size):
            chunk = qids[i : i + chunk_size]
            values = " ".join(f"wd:{q}" for q in chunk)
            prop_values = " ".join(f"wdt:{p}" for p in property_ids)

            query = f"""
            SELECT ?item ?prop ?value ?valueLabel ?valueCoord WHERE {{
              VALUES ?item {{ {values} }}
              VALUES ?prop {{ {prop_values} }}
              ?item ?prop ?value .
              OPTIONAL {{ ?value wdt:P625 ?valueCoord . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            """

            bindings = self._execute_query(query)
            for b in bindings:
                item_qid = b.get("item", {}).get("value", "").split("/")[-1]
                prop = b.get("prop", {}).get("value", "").split("/")[-1]
                val_uri = b.get("value", {}).get("value", "")
                val_label = b.get("valueLabel", {}).get("value", "")
                val_qid = val_uri.split("/")[-1] if "/entity/" in val_uri else None
                val_coord_raw = b.get("valueCoord", {}).get("value", "")
                val_coords = self._parse_point_wkt(val_coord_raw)

                if item_qid not in qid_to_item:
                    continue

                props = qid_to_item[item_qid]["properties"]
                if prop not in props:
                    props[prop] = []

                entry = {
                    "qid": val_qid,
                    "label": val_label,
                    "uri": val_uri,
                }
                if val_coords:
                    entry["coords"] = val_coords
                props[prop].append(entry)

            if i + chunk_size < len(qids):
                time.sleep(2)

        return items

    def fetch_aliases(self, qids: list[str]) -> dict[str, list[str]]:
        """Fetch alternative names / aliases for a batch of QIDs."""
        result: dict[str, list[str]] = {}
        chunk_size = 50

        for i in range(0, len(qids), chunk_size):
            chunk = qids[i : i + chunk_size]
            values = " ".join(f"wd:{q}" for q in chunk)

            query = f"""
            SELECT ?item ?alias WHERE {{
              VALUES ?item {{ {values} }}
              ?item skos:altLabel ?alias .
              FILTER(LANG(?alias) = "{settings.wikipedia_language}")
            }}
            """

            bindings = self._execute_query(query)
            for b in bindings:
                qid = b.get("item", {}).get("value", "").split("/")[-1]
                alias = b.get("alias", {}).get("value", "")
                if qid not in result:
                    result[qid] = []
                result[qid].append(alias)

        return result

    def _enrich_geoshapes(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Resolve Commons geoshapes into GeoJSON geometry objects."""
        for item in items:
            geoshape = self._extract_geoshape_from_properties(item.get("properties", {}))
            if not geoshape:
                continue
            item["geoshape"] = geoshape
            territory_geojson = self.geoshapes.resolve_geometry(geoshape)
            if territory_geojson:
                item["territory_geojson"] = territory_geojson
        return items

    @staticmethod
    def _extract_geoshape_from_properties(properties: dict[str, list[dict[str, Any]]]) -> str | None:
        """Extract a Commons Data:*.map title from enriched P3896 values."""
        values = properties.get("P3896", [])
        for value in values:
            uri = value.get("uri") or ""
            label = value.get("label") or ""
            for candidate in (label, uri):
                if isinstance(candidate, str) and candidate.startswith("Data:") and candidate.endswith(".map"):
                    return candidate
        return None
