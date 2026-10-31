"""Tags-only Overpass queries against OpenHistoricalMap (no geometry is fetched)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import requests

from pipeline.ohm_borders.fetcher import OVERPASS_URL
from pipeline.ohm_links.records import OSM_TYPES

logger = logging.getLogger(__name__)

BOUNDARIES_QUERY = '[out:json][timeout:1800];relation["boundary"="administrative"];out tags;'
PLACES_WITH_WIKIDATA_QUERY = (
    '[out:json][timeout:1800];('
    'node["place"]["wikidata"];way["place"]["wikidata"];relation["place"]["wikidata"];'
    ');out tags;'
)

_ID_LINE_PATTERN = re.compile(r"(node|way|relation)/(\d+)")


def ids_queries(ids: Iterable[tuple[str, int]], batch_size: int = 500) -> Iterator[str]:
    """Yield tags-only queries for explicit (osm_type, osm_id) pairs, at most `batch_size` ids each.

    Ids are de-duplicated and ordered node, way, relation (then by id) so batches are deterministic.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")

    unique: set[tuple[str, int]] = set()
    for osm_type, osm_id in ids:
        if osm_type not in OSM_TYPES:
            raise ValueError(f"Unsupported OSM type: {osm_type!r}")
        unique.add((osm_type, int(osm_id)))

    ordered = sorted(unique, key=lambda pair: (OSM_TYPES.index(pair[0]), pair[1]))

    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        statements = []
        for osm_type in OSM_TYPES:
            type_ids = [str(osm_id) for batch_type, osm_id in batch if batch_type == osm_type]
            if type_ids:
                statements.append(f"{osm_type}(id:{','.join(type_ids)});")
        yield f"[out:json][timeout:600];({''.join(statements)});out tags;"


def fetch_elements(query: str, post=requests.post) -> list[dict[str, Any]]:
    """Run one Overpass query and return its elements.

    Overpass reports timeouts and memory exhaustion as a `remark` on an HTTP 200 response with
    partial (often empty) elements; that raises instead of silently returning partial data.
    """
    response = post(
        OVERPASS_URL,
        data={"data": query},
        timeout=1800,
        headers={"User-Agent": "history-mapped-Pipeline/1.0"},
    )
    response.raise_for_status()
    payload = response.json()

    remark = payload.get("remark")
    if isinstance(remark, str) and "runtime error" in remark:
        raise RuntimeError(f"Overpass query failed: {remark}")

    return payload["elements"]


def read_ids_file(path: str | Path) -> list[tuple[str, int]]:
    """Read `type/id` lines (one per line) into (osm_type, osm_id) pairs.

    Blank lines are ignored; lines that are not `node|way|relation/<digits>` are skipped with a warning.
    """
    ids: list[tuple[str, int]] = []
    skipped = 0

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _ID_LINE_PATTERN.fullmatch(line)
        if match is None:
            skipped += 1
            continue
        ids.append((match.group(1), int(match.group(2))))

    if skipped:
        logger.warning("Skipped %d unsupported line(s) in %s", skipped, path)

    return ids
