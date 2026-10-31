"""Tags-only Overpass queries against OpenHistoricalMap (no geometry is fetched)."""

from __future__ import annotations

import logging
import re
import time
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

RETRY_ATTEMPTS = 5
RETRY_BASE_DELAY_SECONDS = 10
RETRY_MAX_DELAY_SECONDS = 120

_ID_LINE_PATTERN = re.compile(r"(node|way|relation)/([0-9]+)")


class OverpassError(RuntimeError):
    """A transient Overpass failure: HTTP 429/5xx, or a `runtime error` remark on HTTP 200."""


def id_batches(ids: Iterable[tuple[str, int]], batch_size: int = 500) -> Iterator[list[tuple[str, int]]]:
    """Yield de-duplicated (osm_type, osm_id) pairs ordered node, way, relation (then id), `batch_size` at a time."""
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")

    unique: set[tuple[str, int]] = set()
    for osm_type, osm_id in ids:
        if osm_type not in OSM_TYPES:
            raise ValueError(f"Unsupported OSM type: {osm_type!r}")
        unique.add((osm_type, int(osm_id)))

    ordered = sorted(unique, key=lambda pair: (OSM_TYPES.index(pair[0]), pair[1]))
    for start in range(0, len(ordered), batch_size):
        yield ordered[start : start + batch_size]


def ids_query(batch: list[tuple[str, int]]) -> str:
    """Build one tags-only query for a batch of (osm_type, osm_id) pairs, grouped by type."""
    statements = []
    for osm_type in OSM_TYPES:
        type_ids = [str(osm_id) for batch_type, osm_id in batch if batch_type == osm_type]
        if type_ids:
            statements.append(f"{osm_type}(id:{','.join(type_ids)});")
    return f"[out:json][timeout:600];({''.join(statements)});out tags;"


def ids_queries(ids: Iterable[tuple[str, int]], batch_size: int = 500) -> Iterator[str]:
    """Yield tags-only queries for explicit (osm_type, osm_id) pairs, at most `batch_size` ids each."""
    for batch in id_batches(ids, batch_size):
        yield ids_query(batch)


def _fetch_once(query: str, post) -> list[dict[str, Any]]:
    response = post(
        OVERPASS_URL,
        data={"data": query},
        timeout=1800,
        headers={"User-Agent": "history-mapped-Pipeline/1.0"},
    )
    status = response.status_code
    if status == 429 or status >= 500:
        raise OverpassError(f"Overpass returned HTTP {status}")
    response.raise_for_status()
    payload = response.json()

    # Overpass reports timeouts and memory exhaustion as a remark on HTTP 200 with partial elements.
    remark = payload.get("remark")
    if isinstance(remark, str) and "runtime error" in remark:
        raise OverpassError(f"Overpass query failed: {remark}")

    return payload["elements"]


def fetch_elements(
    query: str,
    post=requests.post,
    sleep=time.sleep,
    attempts: int = RETRY_ATTEMPTS,
) -> list[dict[str, Any]]:
    """Run one Overpass query and return its elements.

    Transient failures (HTTP 429/5xx, timeouts, connection errors, `runtime error` remarks) are retried
    with exponential backoff (10 s doubling, capped at 120 s); the last failure is re-raised.
    Other HTTP errors raise immediately.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, got {attempts}")

    delay = RETRY_BASE_DELAY_SECONDS
    for attempt in range(1, attempts + 1):
        try:
            return _fetch_once(query, post)
        except (OverpassError, requests.Timeout, requests.ConnectionError) as exc:
            if attempt == attempts:
                raise
            logger.warning(
                "Overpass attempt %d/%d failed (%s); retrying in %d s", attempt, attempts, exc, delay
            )
            sleep(delay)
            delay = min(delay * 2, RETRY_MAX_DELAY_SECONDS)

    raise AssertionError("unreachable")  # the last attempt either returns or re-raises


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
