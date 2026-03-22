"""Wikimedia Commons geoshape resolver.

Resolves Wikidata `P3896` geoshape values like `Data:NewYork.map`
into plain GeoJSON geometry objects suitable for PostGIS
`ST_GeomFromGeoJSON(...)`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from ratelimit import limits, sleep_and_retry

from pipeline.config import settings

logger = logging.getLogger(__name__)

COMMONS_RAW_ENDPOINT = "https://commons.wikimedia.org/w/index.php"


class GeoshapeResolver:
    """Fetch and normalize Commons Data:*.map geoshapes."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.wikidata_user_agent,
        })
        self._geometry_cache: dict[str, dict[str, Any] | None] = {}

    @sleep_and_retry
    @limits(calls=settings.commons_rpm, period=60)
    def _fetch_raw_map(self, map_title: str) -> dict[str, Any] | None:
        """Fetch raw JSON for a Commons Data:*.map page."""
        try:
            response = self.session.get(
                COMMONS_RAW_ENDPOINT,
                params={"title": map_title, "action": "raw"},
                timeout=45,
            )
            response.raise_for_status()
            return json.loads(response.text)
        except Exception as exc:
            logger.debug(f"Failed to fetch geoshape {map_title}: {exc}")
            return None

    def resolve_geometry(self, map_title: str | None) -> dict[str, Any] | None:
        """Resolve a Commons Data:*.map title into a GeoJSON geometry object."""
        if not map_title:
            return None
        if map_title in self._geometry_cache:
            return self._geometry_cache[map_title]

        raw = self._fetch_raw_map(map_title)
        geometry = self._extract_geometry(raw)
        self._geometry_cache[map_title] = geometry
        return geometry

    def _extract_geometry(self, raw: dict[str, Any] | None) -> dict[str, Any] | None:
        """Normalize Commons map data to a GeoJSON geometry object."""
        if not raw:
            return None

        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict):
            return None

        data_type = data.get("type")
        if data_type == "FeatureCollection":
            return self._normalize_feature_collection(data)
        if data_type in {"Polygon", "MultiPolygon", "LineString", "MultiLineString", "Point", "MultiPoint", "GeometryCollection"}:
            return data

        return None

    def _normalize_feature_collection(self, collection: dict[str, Any]) -> dict[str, Any] | None:
        """Convert a FeatureCollection into a single GeoJSON geometry object."""
        features = collection.get("features", [])
        geometries = [
            feature.get("geometry")
            for feature in features
            if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict)
        ]
        geometries = [geometry for geometry in geometries if geometry.get("type") and geometry.get("coordinates") is not None]

        if not geometries:
            return None
        if len(geometries) == 1:
            return geometries[0]

        if self._all_types(geometries, {"Polygon", "MultiPolygon"}):
            polygons: list[Any] = []
            for geometry in geometries:
                if geometry["type"] == "Polygon":
                    polygons.append(geometry["coordinates"])
                else:
                    polygons.extend(geometry["coordinates"])
            return {"type": "MultiPolygon", "coordinates": polygons}

        if self._all_types(geometries, {"LineString", "MultiLineString"}):
            lines: list[Any] = []
            for geometry in geometries:
                if geometry["type"] == "LineString":
                    lines.append(geometry["coordinates"])
                else:
                    lines.extend(geometry["coordinates"])
            return {"type": "MultiLineString", "coordinates": lines}

        if self._all_types(geometries, {"Point", "MultiPoint"}):
            points: list[Any] = []
            for geometry in geometries:
                if geometry["type"] == "Point":
                    points.append(geometry["coordinates"])
                else:
                    points.extend(geometry["coordinates"])
            return {"type": "MultiPoint", "coordinates": points}

        return {"type": "GeometryCollection", "geometries": geometries}

    @staticmethod
    def _all_types(geometries: list[dict[str, Any]], allowed: set[str]) -> bool:
        return all(geometry.get("type") in allowed for geometry in geometries)
