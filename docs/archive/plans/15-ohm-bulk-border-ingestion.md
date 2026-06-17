# OHM Bulk Border Ingestion — Implementation Plan

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](STATUS.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch all `admin_level=2` boundaries from OHM, enrich with Wikidata metadata, and seed the database with polity entities, `entity_geo_refs`, and time-varying `geometry_periods`.

**Architecture:** New `pipeline/ohm_borders/` Python module (Overpass fetch → Wikidata SPARQL enrich → JSONL emit) + new `pipeline:import-borders` Laravel command (reuses existing Actions, creates `geometry_periods` per chronology stage).

**Tech Stack:** Python — `requests`, `shapely`, `SPARQLWrapper`, `click`, `orjson`; PHP 8.4 / Laravel 13 / PostGIS; Docker Compose for artisan commands.

**Spec:** `docs/superpowers/specs/2026-04-09-ohm-bulk-border-ingestion-design.md`

---

## Task 1: OHM Date Parser

**Files:**
- Create: `pipeline/ohm_borders/__init__.py`
- Create: `pipeline/ohm_borders/date_parser.py`
- Create: `pipeline/tests/test_ohm_borders_date_parser.py`

### Why first
Every subsequent module depends on converting OHM's partial/BCE date strings to signed integer years. Isolating it lets us verify correctness before any real data flows through.

- [ ] **1.1 Write failing tests**

```python
# pipeline/tests/test_ohm_borders_date_parser.py
from pipeline.ohm_borders.date_parser import parse_start_year, parse_end_year

def test_full_date_ce():
    assert parse_start_year("1908-10-05") == 1908

def test_full_date_bce():
    assert parse_start_year("-0500-01-01") == -500

def test_year_only():
    assert parse_start_year("1908") == 1908
    assert parse_end_year("1908") == 1908

def test_partial_year_month_start():
    # Partial start_date → floor: first day of month → year unchanged
    assert parse_start_year("1908-10") == 1908

def test_partial_year_month_end():
    # Partial end_date → ceiling: last day of month → year unchanged
    assert parse_end_year("1908-10") == 1908

def test_none_returns_none():
    assert parse_start_year(None) is None
    assert parse_end_year(None) is None

def test_empty_returns_none():
    assert parse_start_year("") is None

def test_deeply_bce():
    assert parse_start_year("-3000") == -3000
```

- [ ] **1.2 Run tests to confirm they fail**

```bash
cd C:\Users\Achi\Code\FL\history-mapped
python -m pytest pipeline/tests/test_ohm_borders_date_parser.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **1.3 Create package marker and implement date parser**

```python
# pipeline/ohm_borders/__init__.py
```

```python
# pipeline/ohm_borders/date_parser.py
"""Parse OHM ISO 8601 date strings (including partial and BCE) to signed integer years."""
from __future__ import annotations
import re

_YEAR_RE = re.compile(r"^(-?\d+)")


def parse_start_year(raw: str | None) -> int | None:
    """Extract the year from an OHM start_date string. Partial dates → floor year."""
    if not raw:
        return None
    m = _YEAR_RE.match(raw.strip())
    if not m:
        return None
    return int(m.group(1))


def parse_end_year(raw: str | None) -> int | None:
    """Extract the year from an OHM end_date string. Partial dates → ceiling year.

    For end dates the year is the same whether the date is partial or full —
    the difference only matters at sub-year granularity which we don't store.
    """
    if not raw:
        return None
    m = _YEAR_RE.match(raw.strip())
    if not m:
        return None
    return int(m.group(1))
```

- [ ] **1.4 Run tests — expect all pass**

```bash
python -m pytest pipeline/tests/test_ohm_borders_date_parser.py -v
```

Expected: 8 passed.

- [ ] **1.5 Commit**

```bash
git add pipeline/ohm_borders/__init__.py pipeline/ohm_borders/date_parser.py pipeline/tests/test_ohm_borders_date_parser.py
git commit -m "feat(pipeline): add ohm_borders package and date parser"
```

---

## Task 2: OHM Overpass Fetcher

**Files:**
- Create: `pipeline/ohm_borders/fetcher.py`
- Create: `pipeline/tests/test_ohm_borders_fetcher.py`
- Modify: `pipeline/requirements.txt` — add `shapely>=2.0.0`

### What it does
- POST the global admin_level=2 Overpass query
- Parse the `elements` array, separating boundary relations from chronology super-relations
- Assemble ring geometry for each relation using shapely; log and skip on failure
- Return a structured dict per polity: `{relation_id, tags, stages[{relation_id, tags, geometry}]}`

- [ ] **2.1 Write failing tests using a small fixture**

```python
# pipeline/tests/test_ohm_borders_fetcher.py
import json, pathlib
from unittest.mock import patch, MagicMock
from pipeline.ohm_borders.fetcher import (
    parse_elements,
    assemble_geometry,
)

# Minimal fixture: one standalone boundary relation with two outer way members
BOUNDARY_FIXTURE = {
    "elements": [
        {
            "type": "relation",
            "id": 100,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Testland",
                "wikidata": "Q999",
                "start_date": "1900",
                "end_date": "1950",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 1, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 1.0, "lon": 0.0},
                        {"lat": 1.0, "lon": 1.0},
                    ],
                },
                {
                    "type": "way", "ref": 2, "role": "outer",
                    "geometry": [
                        {"lat": 1.0, "lon": 1.0},
                        {"lat": 0.0, "lon": 1.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                },
            ],
        }
    ]
}

CHRONOLOGY_FIXTURE = {
    "elements": [
        # The super-relation (chronology)
        {
            "type": "relation",
            "id": 200,
            "tags": {
                "type": "chronology",
                "boundary": "administrative",
                "name": "Evolving State",
                "wikidata": "Q1000",
            },
            "members": [
                {"type": "relation", "ref": 201, "role": ""},
                {"type": "relation", "ref": 202, "role": ""},
            ],
        },
        # Stage 1
        {
            "type": "relation",
            "id": 201,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1800",
                "end_date": "1850",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 10, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 2.0, "lon": 0.0},
                        {"lat": 2.0, "lon": 2.0},
                        {"lat": 0.0, "lon": 2.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                }
            ],
        },
        # Stage 2
        {
            "type": "relation",
            "id": 202,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1850",
                "end_date": "1900",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 11, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 3.0, "lon": 0.0},
                        {"lat": 3.0, "lon": 3.0},
                        {"lat": 0.0, "lon": 3.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                }
            ],
        },
    ]
}


def test_parse_elements_standalone():
    polities = parse_elements(BOUNDARY_FIXTURE["elements"])
    assert len(polities) == 1
    p = polities[0]
    assert p["relation_id"] == 100
    assert p["tags"]["wikidata"] == "Q999"
    assert len(p["stages"]) == 1
    assert p["stages"][0]["tags"]["start_date"] == "1900"


def test_parse_elements_chronology():
    polities = parse_elements(CHRONOLOGY_FIXTURE["elements"])
    assert len(polities) == 1
    p = polities[0]
    assert p["relation_id"] == 200
    assert p["tags"]["wikidata"] == "Q1000"
    assert len(p["stages"]) == 2
    assert p["stages"][0]["tags"]["start_date"] == "1800"


def test_assemble_geometry_closed_outer():
    members = BOUNDARY_FIXTURE["elements"][0]["members"]
    geojson = assemble_geometry(members)
    assert geojson is not None
    assert geojson["type"] in ("Polygon", "MultiPolygon")


def test_assemble_geometry_returns_none_on_empty():
    assert assemble_geometry([]) is None
```

- [ ] **2.2 Run tests to confirm they fail**

```bash
python -m pytest pipeline/tests/test_ohm_borders_fetcher.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **2.3 Add shapely to requirements.txt**

```
# Geometry assembly for OHM ring-stitching
shapely>=2.0.0
```

- [ ] **2.4 Implement fetcher**

```python
# pipeline/ohm_borders/fetcher.py
"""Fetch all admin_level=2 boundary relations from OHM via Overpass API."""
from __future__ import annotations

import logging
from typing import Any

import requests
from shapely.geometry import mapping, MultiPolygon, Polygon
from shapely.ops import unary_union

from pipeline.config import settings

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.openhistoricalmap.org/api/interpreter"

GLOBAL_QUERY = """
[out:json][timeout:1800];
relation["boundary"="administrative"]["admin_level"="2"];
out geom;
"""


def fetch_raw(query: str = GLOBAL_QUERY) -> dict[str, Any]:
    """POST a query to OHM Overpass and return the parsed JSON."""
    resp = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=1800,
        headers={"User-Agent": "history-mapped-Pipeline/1.0"},
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]


def parse_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse Overpass elements into a list of polity dicts.

    Each polity dict has:
      relation_id: int
      tags: dict
      stages: list[{relation_id, tags, geometry}]  — one per time-slice

    Chronology super-relations become one polity with N stages.
    Standalone boundary relations become one polity with 1 stage.
    """
    # Index all relations by id
    by_id: dict[int, dict[str, Any]] = {
        el["id"]: el for el in elements if el.get("type") == "relation"
    }

    # Find chronology super-relations
    chronology_ids: set[int] = set()
    member_ids: set[int] = set()

    for rel in by_id.values():
        if rel.get("tags", {}).get("type") == "chronology":
            chronology_ids.add(rel["id"])
            for m in rel.get("members", []):
                if m.get("type") == "relation":
                    member_ids.add(m["ref"])

    polities: list[dict[str, Any]] = []

    # Process chronology super-relations
    for cid in chronology_ids:
        chron = by_id[cid]
        stages = []
        for m in chron.get("members", []):
            if m.get("type") != "relation":
                continue
            stage_rel = by_id.get(m["ref"])
            if stage_rel is None:
                continue
            geojson = assemble_geometry(stage_rel.get("members", []))
            stages.append({
                "relation_id": stage_rel["id"],
                "tags": stage_rel.get("tags", {}),
                "geometry": geojson,
            })
        polities.append({
            "relation_id": cid,
            "tags": chron.get("tags", {}),
            "stages": stages,
        })

    # Standalone boundaries (not a chronology member)
    for rel in by_id.values():
        if rel["id"] in chronology_ids or rel["id"] in member_ids:
            continue
        tags = rel.get("tags", {})
        if tags.get("boundary") != "administrative":
            continue
        geojson = assemble_geometry(rel.get("members", []))
        polities.append({
            "relation_id": rel["id"],
            "tags": tags,
            "stages": [{"relation_id": rel["id"], "tags": tags, "geometry": geojson}],
        })

    return polities


def assemble_geometry(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Stitch member-way coordinates into a GeoJSON Polygon or MultiPolygon.

    Uses shapely to handle ring closure, orientation, and invalid rings.
    Returns None if no usable outer ring can be assembled.
    """
    outer_coords: list[list[tuple[float, float]]] = []
    inner_coords: list[list[tuple[float, float]]] = []

    for m in members:
        if m.get("type") != "way":
            continue
        role = m.get("role", "outer")
        geometry = m.get("geometry", [])
        coords = [(pt["lon"], pt["lat"]) for pt in geometry if "lon" in pt and "lat" in pt]
        if len(coords) < 3:
            continue
        if role == "inner":
            inner_coords.append(coords)
        else:
            outer_coords.append(coords)

    if not outer_coords:
        return None

    try:
        outers = [Polygon(c) for c in outer_coords if len(c) >= 3]
        inners = [Polygon(c) for c in inner_coords if len(c) >= 3]

        # Merge outer rings
        merged = unary_union([p for p in outers if p.is_valid])
        # Subtract inner rings (holes)
        for hole in inners:
            if hole.is_valid:
                merged = merged.difference(hole)

        if merged.is_empty:
            return None

        # Force MultiPolygon for consistency
        if isinstance(merged, Polygon):
            merged = MultiPolygon([merged])

        return mapping(merged)  # type: ignore[return-value]
    except Exception as exc:
        logger.warning(f"Geometry assembly failed: {exc}")
        return None
```

- [ ] **2.5 Run tests — expect all pass**

```bash
python -m pytest pipeline/tests/test_ohm_borders_fetcher.py -v
```

Expected: 4 passed.

- [ ] **2.6 Commit**

```bash
git add pipeline/ohm_borders/fetcher.py pipeline/tests/test_ohm_borders_fetcher.py pipeline/requirements.txt
git commit -m "feat(pipeline): add OHM Overpass fetcher with shapely geometry assembly"
```

---

## Task 3: Wikidata Batch Enricher

**Files:**
- Create: `pipeline/ohm_borders/enricher.py`
- Create: `pipeline/tests/test_ohm_borders_enricher.py`

### What it does
Takes a list of Wikidata QIDs (from OHM `wikidata` tags), runs a SPARQL VALUES query in batches of 50, and returns a dict `{QID: {name_en, aliases_en, description, entity_type, temporal_start, temporal_end}}`.

- [ ] **3.1 Write failing tests (uses mocked SPARQL response)**

```python
# pipeline/tests/test_ohm_borders_enricher.py
from unittest.mock import patch, MagicMock
import json
from pipeline.ohm_borders.enricher import batch_enrich_qids, _build_sparql_query

def test_build_sparql_query_includes_qids():
    query = _build_sparql_query(["Q1", "Q2"])
    assert "wd:Q1" in query
    assert "wd:Q2" in query

def _mock_sparql_result(qid: str, label: str) -> dict:
    return {
        "polity": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "polityLabel": {"value": label},
        "polityDescription": {"value": "A historic state"},
        "altLabel": {"value": "AltName"},
        "inception": {"value": "1908-01-01T00:00:00Z"},
        "dissolution": {"value": "1946-01-01T00:00:00Z"},
    }

def test_batch_enrich_returns_keyed_by_qid():
    mock_results = [_mock_sparql_result("Q219", "Kingdom of Bulgaria")]
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = mock_results
        result = batch_enrich_qids(["Q219"])
    assert "Q219" in result
    assert result["Q219"]["name_en"] == "Kingdom of Bulgaria"
    assert result["Q219"]["temporal_start"] == "1908"

def test_batch_enrich_returns_empty_on_missing_qid():
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = []
        result = batch_enrich_qids(["Q99999999"])
    assert result == {}

def test_batch_size_splits_large_list():
    qids = [f"Q{i}" for i in range(120)]
    calls = []
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = []
        from pipeline.ohm_borders.enricher import batch_enrich_qids
        batch_enrich_qids(qids, batch_size=50)
        assert mock_q.call_count == 3  # 50 + 50 + 20
```

- [ ] **3.2 Run tests — expect ImportError**

```bash
python -m pytest pipeline/tests/test_ohm_borders_enricher.py -v 2>&1 | head -10
```

- [ ] **3.3 Implement enricher**

```python
# pipeline/ohm_borders/enricher.py
"""Fetch Wikidata entity metadata for a batch of QIDs."""
from __future__ import annotations

import logging
from typing import Any

from SPARQLWrapper import SPARQLWrapper, JSON

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
_USER_AGENT = "history-mapped-Pipeline/1.0 (https://history-mapped.example)"

_SPARQL_TEMPLATE = """
SELECT ?polity ?polityLabel ?polityDescription
       (GROUP_CONCAT(DISTINCT ?altLabelVal; SEPARATOR="||") AS ?altLabel)
       ?inception ?dissolution
WHERE {{
  VALUES ?polity {{ {qid_list} }}
  OPTIONAL {{ ?polity wdt:P571 ?inception. }}
  OPTIONAL {{ ?polity wdt:P576 ?dissolution. }}
  OPTIONAL {{ ?polity skos:altLabel ?altLabelVal. FILTER(LANG(?altLabelVal)="en") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?polity ?polityLabel ?polityDescription ?inception ?dissolution
"""


def _build_sparql_query(qids: list[str]) -> str:
    qid_list = " ".join(f"wd:{q}" for q in qids)
    return _SPARQL_TEMPLATE.format(qid_list=qid_list)


def _sparql_query(query: str) -> list[dict[str, Any]]:
    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]  # type: ignore[index]


def _extract_year(iso_val: str | None) -> str | None:
    """Extract 4(+)-digit year from Wikidata datetime string."""
    if not iso_val:
        return None
    # e.g. "1908-01-01T00:00:00Z" → "1908"
    import re
    m = re.match(r"(-?\d+)", iso_val)
    return m.group(1) if m else None


def batch_enrich_qids(
    qids: list[str],
    batch_size: int = 50,
) -> dict[str, dict[str, Any]]:
    """Return {QID: metadata_dict} for all QIDs that Wikidata knows about."""
    results: dict[str, dict[str, Any]] = {}
    qids = list(dict.fromkeys(qids))  # deduplicate, preserve order

    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        try:
            bindings = _sparql_query(_build_sparql_query(batch))
        except Exception as exc:
            logger.warning(f"SPARQL batch failed for batch starting at {i}: {exc}")
            continue

        for row in bindings:
            uri = row.get("polity", {}).get("value", "")
            qid = uri.rsplit("/", 1)[-1]
            alt_raw = row.get("altLabel", {}).get("value", "")
            aliases = [a.strip() for a in alt_raw.split("||") if a.strip()] if alt_raw else []

            results[qid] = {
                "name_en": row.get("polityLabel", {}).get("value"),
                "description": row.get("polityDescription", {}).get("value"),
                "aliases_en": aliases,
                "temporal_start": _extract_year(row.get("inception", {}).get("value")),
                "temporal_end": _extract_year(row.get("dissolution", {}).get("value")),
            }

    return results
```

- [ ] **3.4 Run tests — expect all pass**

```bash
python -m pytest pipeline/tests/test_ohm_borders_enricher.py -v
```

Expected: 4 passed.

- [ ] **3.5 Commit**

```bash
git add pipeline/ohm_borders/enricher.py pipeline/tests/test_ohm_borders_enricher.py
git commit -m "feat(pipeline): add Wikidata batch enricher for OHM QIDs"
```

---

## Task 4: OHM → JSONL Mapper

**Files:**
- Create: `pipeline/ohm_borders/mapper.py`
- Create: `pipeline/tests/test_ohm_borders_mapper.py`

### What it does
Takes a `polity` dict from the fetcher and optional Wikidata metadata dict, and produces one JSONL entity record including `_geometry_periods[]`.

- [ ] **4.1 Write failing tests**

```python
# pipeline/tests/test_ohm_borders_mapper.py
from pipeline.ohm_borders.mapper import map_polity_to_jsonl

BASE_POLITY = {
    "relation_id": 100,
    "tags": {
        "name": "Testland",
        "name:en": "Testland (EN)",
        "wikidata": "Q999",
        "start_date": "1900",
        "end_date": "1950",
    },
    "stages": [
        {
            "relation_id": 100,
            "tags": {"start_date": "1900", "end_date": "1950"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0,0],[1,0],[1,1],[0,0]]]]},
        }
    ],
}

CHRON_POLITY = {
    "relation_id": 200,
    "tags": {"name": "Evolving State", "wikidata": "Q1000"},
    "stages": [
        {
            "relation_id": 201,
            "tags": {"start_date": "1800", "end_date": "1850"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0,0],[2,0],[2,2],[0,0]]]]},
        },
        {
            "relation_id": 202,
            "tags": {"start_date": "1850", "end_date": "1900"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0,0],[3,0],[3,3],[0,0]]]]},
        },
    ],
}

WD_META = {
    "Q999": {
        "name_en": "Testland",
        "description": "A test polity",
        "aliases_en": ["TL"],
        "temporal_start": "1900",
        "temporal_end": "1950",
    },
    "Q1000": {
        "name_en": "Evolving State",
        "description": None,
        "aliases_en": [],
        "temporal_start": "1800",
        "temporal_end": "1900",
    },
}


def test_map_standalone_basic_fields():
    rec = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert rec["entity_type"] == "political_entity"
    assert rec["entity_group"] == "POLITY"
    assert rec["wikidata_id"] == "Q999"
    assert rec["name"] == "Testland"
    assert rec["verification_status"] == "ohm_draft"


def test_map_standalone_geometry_period():
    rec = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert len(rec["_geometry_periods"]) == 1
    gp = rec["_geometry_periods"][0]
    assert gp["ohm_relation_id"] == "100"
    assert gp["start_year"] == 1900
    assert gp["end_year"] == 1950
    assert gp["geojson"]["type"] == "MultiPolygon"


def test_map_chronology_produces_multiple_periods():
    rec = map_polity_to_jsonl(CHRON_POLITY, WD_META)
    assert len(rec["_geometry_periods"]) == 2
    assert rec["_geometry_periods"][0]["start_year"] == 1800
    assert rec["_geometry_periods"][1]["start_year"] == 1850


def test_map_without_wikidata_uses_ohm_name():
    rec = map_polity_to_jsonl(BASE_POLITY, {})
    # No wikidata metadata — fall back to OHM name:en or name
    assert rec["name"] in ("Testland (EN)", "Testland")
    assert rec["wikidata_id"] == "Q999"


def test_map_ohm_relation_id_stored():
    rec = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert rec["_ohm_relation_id"] == "100"
```

- [ ] **4.2 Run tests — expect ImportError**

```bash
python -m pytest pipeline/tests/test_ohm_borders_mapper.py -v 2>&1 | head -10
```

- [ ] **4.3 Implement mapper**

```python
# pipeline/ohm_borders/mapper.py
"""Map a parsed OHM polity dict + Wikidata metadata to a JSONL entity record."""
from __future__ import annotations
from typing import Any
from pipeline.ohm_borders.date_parser import parse_start_year, parse_end_year


def _pick_name(tags: dict[str, Any], wd_meta: dict[str, Any] | None) -> str:
    if wd_meta and wd_meta.get("name_en"):
        return wd_meta["name_en"]
    return tags.get("name:en") or tags.get("name") or "Unknown"


def map_polity_to_jsonl(
    polity: dict[str, Any],
    wikidata_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Convert a polity dict from the fetcher into a JSONL entity record."""
    tags = polity["tags"]
    qid = tags.get("wikidata")
    wd_meta = wikidata_index.get(qid) if qid else None

    name = _pick_name(tags, wd_meta)
    aliases: list[str] = []
    if wd_meta and wd_meta.get("aliases_en"):
        aliases = wd_meta["aliases_en"]

    temporal_start = (wd_meta or {}).get("temporal_start") or tags.get("start_date")
    temporal_end = (wd_meta or {}).get("temporal_end") or tags.get("end_date")

    geometry_periods: list[dict[str, Any]] = []
    for stage in polity.get("stages", []):
        stage_tags = stage.get("tags", {})
        raw_start = stage_tags.get("start_date") or tags.get("start_date")
        raw_end = stage_tags.get("end_date") or tags.get("end_date")
        start_year = parse_start_year(raw_start)
        end_year = parse_end_year(raw_end)
        geojson = stage.get("geometry")

        label_parts = [name]
        if start_year is not None and end_year is not None:
            label_parts.append(f"({start_year}–{end_year})")
        label = " ".join(label_parts)

        geometry_periods.append({
            "ohm_relation_id": str(stage["relation_id"]),
            "external_type": "relation",
            "start_year": start_year,
            "end_year": end_year,
            "start_date": raw_start,
            "end_date": raw_end,
            "geojson": geojson,
            "label": label,
            "external_tags": stage_tags,
        })

    record: dict[str, Any] = {
        "name": name,
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": qid,
        "alternative_names": aliases,
        "summary": (wd_meta or {}).get("description"),
        "temporal_start": temporal_start,
        "temporal_end": temporal_end,
        "verification_status": "ohm_draft",
        "confidence": "medium",
        "location_method": "ohm_nominatim",
        "location_confidence": "high",
        "_ohm_relation_id": str(polity["relation_id"]),
        "_geometry_periods": geometry_periods,
    }

    return record
```

- [ ] **4.4 Run tests — expect all pass**

```bash
python -m pytest pipeline/tests/test_ohm_borders_mapper.py -v
```

Expected: 5 passed.

- [ ] **4.5 Commit**

```bash
git add pipeline/ohm_borders/mapper.py pipeline/tests/test_ohm_borders_mapper.py
git commit -m "feat(pipeline): add OHM→JSONL mapper with geometry_periods support"
```

---

## Task 5: CLI Command + Requirements

**Files:**
- Modify: `pipeline/__main__.py`
- Modify: `pipeline/requirements.txt` (shapely already added in Task 2)

- [ ] **5.1 Add `borders` command to `pipeline/__main__.py`**

After the existing `@cli.command()` blocks, add:

```python
@cli.command()
@click.option("--output", default=None, help="Output JSONL path (default: output/ohm_borders.jsonl)")
@click.option("--query-file", default=None, type=click.Path(exists=True), help="Override Overpass query file")
@click.option("--no-enrich", is_flag=True, help="Skip Wikidata enrichment (faster, fewer fields)")
def borders(output, query_file, no_enrich):
    """Fetch all admin_level=2 OHM borders and emit a JSONL file."""
    import orjson
    from pathlib import Path
    from pipeline.ohm_borders.fetcher import fetch_raw, parse_elements, GLOBAL_QUERY
    from pipeline.ohm_borders.enricher import batch_enrich_qids
    from pipeline.ohm_borders.mapper import map_polity_to_jsonl

    out = Path(output or "output/ohm_borders.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    query = GLOBAL_QUERY
    if query_file:
        query = Path(query_file).read_text()

    console.print("[bold]Fetching OHM admin_level=2 boundaries…[/bold]")
    console.print(f"  Overpass endpoint: {query[:60].strip()}…")
    raw = fetch_raw(query)
    elements = raw.get("elements", [])
    console.print(f"  → {len(elements)} elements returned")

    polities = parse_elements(elements)
    console.print(f"  → {len(polities)} polities parsed")

    wikidata_index: dict = {}
    if not no_enrich:
        qids = [p["tags"]["wikidata"] for p in polities if p["tags"].get("wikidata")]
        qids = list(dict.fromkeys(qids))
        console.print(f"  Enriching {len(qids)} QIDs from Wikidata…")
        wikidata_index = batch_enrich_qids(qids)
        console.print(f"  → {len(wikidata_index)} QIDs enriched")

    with open(out, "wb") as f:
        for polity in polities:
            record = map_polity_to_jsonl(polity, wikidata_index)
            f.write(orjson.dumps(record) + b"\n")

    console.print(f"\n[bold green]Done.[/bold green] Written to {out}")
```

Add the import for `borders` to the cli group (it's a function defined in the same file, so it's auto-registered via `@cli.command()`).

- [ ] **5.2 Smoke-test the CLI (dry run against a tiny Overpass fixture)**

```bash
# Verify CLI registers the command
python -m pipeline --help
# Expected output includes: borders
python -m pipeline borders --help
```

- [ ] **5.3 Commit**

```bash
git add pipeline/__main__.py
git commit -m "feat(pipeline): add borders CLI command"
```

---

## Task 6: Add `ohm_draft` to Laravel VerificationStatus enum

**Files:**
> **Also:** `geometry_periods.provenance_mode` has a CHECK constraint limited to `'derived'` and `'manual'`.
> The job uses `'ohm_import'`, so this migration must also extend that constraint.

- [ ] **6.1 Check existing enum values**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo implode(', ', array_column(App\Enums\VerificationStatus::cases(), 'value'));"
```

- [ ] **6.2 Add `OhmDraft` case to the PHP enum**

Open `api/app/Enums/VerificationStatus.php` and add after the last existing case:

```php
case OhmDraft = 'ohm_draft';
```

- [ ] **6.3 Generate migration**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan make:migration add_ohm_draft_to_verification_status_enum --no-interaction
```

- [ ] **6.4 Implement migration**

In the generated migration file, `up()` and `down()`:

```php
public function up(): void
{
    DB::statement("ALTER TYPE verification_status ADD VALUE IF NOT EXISTS 'ohm_draft'");
    // Extend the provenance_mode CHECK constraint to allow 'ohm_import'
    DB::statement("ALTER TABLE geometry_periods DROP CONSTRAINT IF EXISTS gp_provenance_mode");
    DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_provenance_mode
        CHECK (provenance_mode IN ('derived', 'manual', 'ohm_import'))");
}

public function down(): void
{
    // PostgreSQL cannot remove ENUM values; this is intentionally a no-op.
    // To revert: recreate the type without 'ohm_draft' manually.
    // To revert provenance_mode: drop and recreate constraint without 'ohm_import'.
}
```

- [ ] **6.5 Run migration**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan migrate --no-interaction
```

Expected: 1 migration ran.

- [ ] **6.6 Commit**

```bash
git add api/app/Enums/VerificationStatus.php api/database/migrations/
git commit -m "feat(api): add ohm_draft verification status for bulk OHM imports"
```

---

## Task 7: Laravel `ImportBorderEntityJob`

**Files:**
- Create: `api/app/Jobs/ImportBorderEntityJob.php`
- Create: `api/tests/Feature/Feature/ImportBordersCommandTest.php` (skeleton, extended in Task 8)

The job reuses:
- `CreateEntityAction` / `UpdateEntityAction`
- `CreateEntityGeoRefAction`
- `HydrateEntityGeometryFromGeoRefAction`
- `GeometryPeriod::create(...)` directly (no separate action needed)

- [ ] **7.1 Write failing test covering the happy path**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan make:test Feature/ImportBordersCommandTest --no-interaction
```

```php
// api/tests/Feature/Feature/ImportBordersCommandTest.php
namespace Tests\Feature\Feature;

use App\Enums\VerificationStatus;
use App\Jobs\ImportBorderEntityJob;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportBordersCommandTest extends TestCase
{
    use RefreshDatabase;

    private function makeRecord(array $overrides = []): array
    {
        return array_merge([
            'name' => 'Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q9999',
            'summary' => 'A test polity',
            'temporal_start' => '1900',
            'temporal_end' => '1950',
            'verification_status' => 'ohm_draft',
            'confidence' => 'medium',
            'location_method' => 'ohm_nominatim',
            'location_confidence' => 'high',
            '_ohm_relation_id' => '100',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '100',
                    'external_type' => 'relation',
                    'start_year' => 1900,
                    'end_year' => 1950,
                    'start_date' => '1900',
                    'end_date' => '1950',
                    'geojson' => ['type' => 'MultiPolygon', 'coordinates' => [[[[0,0],[1,0],[1,1],[0,0]]]]],
                    'label' => 'Testland (1900–1950)',
                    'external_tags' => ['name' => 'Testland'],
                ],
            ],
        ], $overrides);
    }

    public function test_job_creates_entity_with_ohm_draft_status(): void
    {
        $record = $this->makeRecord();
        (new ImportBorderEntityJob($record, 'test-batch'))->handle();

        $entity = Entity::query()->where('wikidata_id', 'Q9999')->first();
        $this->assertNotNull($entity);
        $this->assertEquals('ohm_draft', $entity->verification_status->value);
    }

    public function test_job_creates_entity_geo_ref(): void
    {
        $record = $this->makeRecord();
        (new ImportBorderEntityJob($record, 'test-batch'))->handle();

        $entity = Entity::query()->where('wikidata_id', 'Q9999')->firstOrFail();
        $ref = EntityGeoRef::query()->where('entity_id', $entity->entity_id)->first();
        $this->assertNotNull($ref);
        $this->assertEquals('ohm', $ref->provider->value);
        $this->assertEquals('100', $ref->external_id);
        $this->assertEquals('relation', $ref->external_type->value);
    }

    public function test_job_creates_geometry_period_per_stage(): void
    {
        $record = $this->makeRecord();
        (new ImportBorderEntityJob($record, 'test-batch'))->handle();

        $entity = Entity::query()->where('wikidata_id', 'Q9999')->firstOrFail();
        $periods = GeometryPeriod::query()->where('entity_id', $entity->entity_id)->get();
        $this->assertCount(1, $periods);
        $this->assertEquals(1900, $periods->first()->start_year);
        $this->assertEquals(1950, $periods->first()->end_year);
    }

    public function test_job_skips_duplicate_by_wikidata_id(): void
    {
        $record = $this->makeRecord();
        (new ImportBorderEntityJob($record, 'test-batch'))->handle();
        (new ImportBorderEntityJob($record, 'test-batch-2'))->handle();

        $this->assertCount(1, Entity::query()->where('wikidata_id', 'Q9999')->get());
        $this->assertCount(1, GeometryPeriod::query()
            ->whereHas('entity', fn ($q) => $q->where('wikidata_id', 'Q9999'))
            ->get());
    }

    public function test_job_creates_geometry_period_for_multiple_stages(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q8888',
            '_ohm_relation_id' => '200',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '201', 'external_type' => 'relation',
                    'start_year' => 1800, 'end_year' => 1850,
                    'geojson' => ['type' => 'MultiPolygon', 'coordinates' => [[[[0,0],[2,0],[2,2],[0,0]]]]],
                    'label' => 'Evolving (1800–1850)', 'external_tags' => [],
                ],
                [
                    'ohm_relation_id' => '202', 'external_type' => 'relation',
                    'start_year' => 1850, 'end_year' => 1900,
                    'geojson' => ['type' => 'MultiPolygon', 'coordinates' => [[[[0,0],[3,0],[3,3],[0,0]]]]],
                    'label' => 'Evolving (1850–1900)', 'external_tags' => [],
                ],
            ],
        ]);

        (new ImportBorderEntityJob($record, 'test-batch'))->handle();

        $entity = Entity::query()->where('wikidata_id', 'Q8888')->firstOrFail();
        $this->assertCount(2, GeometryPeriod::query()->where('entity_id', $entity->entity_id)->get());
    }
}
```

- [ ] **7.2 Run tests — expect failures**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php --compact
```

Expected: class not found / method not found errors.

- [ ] **7.3 Implement `ImportBorderEntityJob`**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan make:class app/Jobs/ImportBorderEntityJob --no-interaction
```

Then implement (see full source below — implement in the file):

```php
<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\Actions\EntityGeoRef\CreateEntityGeoRefAction;
use App\Actions\EntityGeoRef\HydrateEntityGeometryFromGeoRefAction;
use App\DTOs\EntityData;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\GeometryPeriod;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class ImportBorderEntityJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;
    public int $backoff = 10;

    /**
     * @param array<string, mixed> $record  Decoded JSONL border record.
     * @param string $batchId
     */
    public function __construct(
        public readonly array $record,
        public readonly string $batchId,
    ) {}

    public function handle(): void
    {
        $name = $this->record['name'] ?? 'unknown';

        try {
            if (! isset($this->record['name'], $this->record['entity_type'], $this->record['entity_group'])) {
                Log::warning('[Borders] Skipped record missing required fields');
                return;
            }

            $ohmRelationId = (string) ($this->record['_ohm_relation_id'] ?? '');
            $geometryPeriods = $this->record['_geometry_periods'] ?? [];

            $entityRecord = $this->record;
            unset($entityRecord['_ohm_relation_id'], $entityRecord['_geometry_periods']);
            $entityRecord['verification_status'] = 'ohm_draft';

            $entityData = EntityData::fromArray($entityRecord);
            $entity = $this->findExisting();

            if ($entity !== null) {
                Log::info("[Borders] Skipped duplicate: {$name} ({$entity->wikidata_id})");
                // Still upsert geometry periods in case this is a re-run
                $this->upsertGeometryPeriods($entity, $geometryPeriods);
                return;
            }

            $entity = app(CreateEntityAction::class)($entityData, "borders:{$this->batchId}");
            Log::info("[Borders] Imported: {$name} → {$entity->entity_id}");

            if ($ohmRelationId !== '') {
                $geoRef = $this->createGeoRef($entity, $ohmRelationId, $geometryPeriods);
                $this->hydrateBaseGeometry($entity, $geoRef, $geometryPeriods);
            }

            $this->upsertGeometryPeriods($entity, $geometryPeriods);

        } catch (\Throwable $e) {
            Log::error("[Borders] Failed to import {$name}: {$e->getMessage()}");
            throw $e;
        }
    }

    private function findExisting(): ?Entity
    {
        $wikidataId = $this->record['wikidata_id'] ?? null;
        if ($wikidataId) {
            return Entity::query()->where('wikidata_id', $wikidataId)->first();
        }
        return null;
    }

    private function createGeoRef(Entity $entity, string $relationId, array $geometryPeriods): EntityGeoRef
    {
        // Use the first stage's dates as the geo-ref temporal bounds
        $firstStage = $geometryPeriods[0] ?? [];
        $lastStage  = $geometryPeriods[count($geometryPeriods) - 1] ?? $firstStage;

        return app(CreateEntityGeoRefAction::class)->__invoke($entity, [
            'provider'          => GeoRefProvider::Ohm->value,
            'external_type'     => GeoRefExternalType::Relation->value,
            'external_id'       => $relationId,
            'match_role'        => GeoRefMatchRole::Primary->value,
            'retrieval_method'  => GeoRefRetrievalMethod::Overpass->value,
            'match_score'       => 1.0,
            'temporal_start_year' => $firstStage['start_year'] ?? null,
            'temporal_end_year'   => $lastStage['end_year'] ?? null,
            'is_active'         => true,
        ]);
    }

    private function hydrateBaseGeometry(Entity $entity, EntityGeoRef $geoRef, array $geometryPeriods): void
    {
        // Use the first stage with geometry as base entity geometry
        foreach ($geometryPeriods as $period) {
            $geojson = $period['geojson'] ?? null;
            if (is_array($geojson)) {
                app(HydrateEntityGeometryFromGeoRefAction::class)->__invoke(
                    $entity, $geoRef, $geojson, 'ohm_nominatim'
                );
                return;
            }
        }
    }

    /** @param array<int, array<string, mixed>> $periods */
    private function upsertGeometryPeriods(Entity $entity, array $periods): void
    {
        foreach ($periods as $period) {
            $startYear = $period['start_year'] ?? null;
            $endYear   = $period['end_year'] ?? null;
            $geojson   = $period['geojson'] ?? null;

            if ($geojson === null) {
                continue;
            }

            // Idempotency: skip if same entity + year range already exists
            $exists = GeometryPeriod::query()
                ->where('entity_id', $entity->entity_id)
                ->where('start_year', $startYear)
                ->where('end_year', $endYear)
                ->exists();

            if ($exists) {
                continue;
            }

            GeometryPeriod::query()->create([
                'entity_id'      => $entity->entity_id,
                'period_type'    => 'territory',
                'start_year'     => $startYear,
                'end_year'       => $endYear,
                'territory_geom' => $geojson,
                'description'    => $period['label'] ?? null,
                'provenance_mode' => 'ohm_import',
                'created_by'     => "borders:{$this->batchId}",
            ]);
        }
    }
}
```

- [ ] **7.4 Run tests — expect all pass**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php --compact
```

Expected: 5 passed.

- [ ] **7.5 Commit**

```bash
git add api/app/Jobs/ImportBorderEntityJob.php api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "feat(api): add ImportBorderEntityJob for OHM bulk border ingestion"
```

---

## Task 8: Laravel `ImportBordersCommand`

**Files:**
- Create: `api/app/Console/Commands/ImportBordersCommand.php`
- Extend: `api/tests/Feature/Feature/ImportBordersCommandTest.php`

- [ ] **8.1 Add command-level tests to existing test file**

Add these test methods to `ImportBordersCommandTest`:

```php
public function test_command_imports_single_jsonl_record(): void
{
    $record = $this->makeRecord(['wikidata_id' => 'Q7777']);
    $jsonl = json_encode($record) . "\n";
    $path = $this->writeTemp($jsonl);

    $this->artisan("pipeline:import-borders {$path} --sync")
        ->assertSuccessful();

    $this->assertDatabaseHas('entities', ['wikidata_id' => 'Q7777']);
}

public function test_command_reports_skipped_duplicates(): void
{
    $record = $this->makeRecord(['wikidata_id' => 'Q6666']);
    $jsonl = json_encode($record) . "\n" . json_encode($record) . "\n";
    $path = $this->writeTemp($jsonl);

    $this->artisan("pipeline:import-borders {$path} --sync")
        ->assertSuccessful();

    $this->assertCount(1, Entity::query()->where('wikidata_id', 'Q6666')->get());
}

/** Write string to a temp file and return path. */
private function writeTemp(string $content): string
{
    $path = storage_path('app/test_borders_' . uniqid() . '.jsonl');
    file_put_contents($path, $content);
    $this->beforeApplicationDestroyed(fn() => @unlink($path));
    return $path;
}
```

- [ ] **8.2 Run new tests — expect failure (command not found)**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php --compact --filter test_command
```

- [ ] **8.3 Generate and implement the command**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan make:command ImportBordersCommand --no-interaction
```

```php
// api/app/Console/Commands/ImportBordersCommand.php
<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\ImportBorderEntityJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class ImportBordersCommand extends Command
{
    protected $signature = 'pipeline:import-borders
        {path : Path to a JSONL file produced by python -m pipeline borders}
        {--sync : Process synchronously instead of dispatching jobs}
        {--batch-id= : Custom batch identifier}';

    protected $description = 'Import OHM border entities from a pipeline JSONL file';

    public function handle(): int
    {
        $path = $this->argument('path');

        if (! file_exists($path)) {
            $this->error("File not found: {$path}");
            return self::FAILURE;
        }

        $sync = (bool) $this->option('sync');
        $batchId = $this->option('batch-id') ?? 'borders-' . now()->format('Ymd-His');
        $this->info("Batch: {$batchId}");

        $handle = fopen($path, 'r');
        if ($handle === false) {
            $this->error("Cannot open file: {$path}");
            return self::FAILURE;
        }

        $imported = 0;
        $skipped = 0;

        while (($line = fgets($handle)) !== false) {
            $line = trim($line);
            if ($line === '') {
                continue;
            }

            $record = json_decode($line, true);
            if (! is_array($record)) {
                $this->warn('  Skipped malformed JSON line');
                $skipped++;
                continue;
            }

            if ($sync) {
                (new ImportBorderEntityJob($record, $batchId))->handle();
            } else {
                ImportBorderEntityJob::dispatch($record, $batchId);
            }

            $imported++;
        }

        fclose($handle);

        $this->info("  Dispatched: {$imported} | Skipped malformed: {$skipped}");
        return self::SUCCESS;
    }
}
```

- [ ] **8.4 Run all tests**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php --compact
```

Expected: 7 passed.

- [ ] **8.5 Run full suite to check for regressions**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --compact
```

Expected: all passing.

- [ ] **8.6 Commit**

```bash
git add api/app/Console/Commands/ImportBordersCommand.php api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "feat(api): add pipeline:import-borders command"
```

---

## Task 9: End-to-End Smoke Test

This task validates the full chain against the real OHM API using a small bbox query (not the global query).

- [ ] **9.1 Run a bbox-limited Overpass fetch (Europe, ~100 relations)**

```bash
# From the repo root
python -m pipeline borders \
  --output output/ohm_borders_smoke.jsonl
# If the global query is too slow for a first test, edit fetcher.GLOBAL_QUERY
# to add a bbox: relation(35,-12,60,40)["boundary"="administrative"]["admin_level"="2"];
```

Note: expect 30–90 seconds for a bbox query. The global query may take 5–15 minutes and should be run only once you're confident in the pipeline.

- [ ] **9.2 Inspect the output**

```bash
# Count records
python -c "import orjson, pathlib; lines=pathlib.Path('output/ohm_borders_smoke.jsonl').read_bytes().splitlines(); print(f'{len(lines)} records')"

# Inspect first record
python -c "import orjson, pathlib; print(orjson.dumps(orjson.loads(pathlib.Path('output/ohm_borders_smoke.jsonl').read_bytes().splitlines()[0]), option=orjson.OPT_INDENT_2).decode())"
```

Expected: each record has `name`, `wikidata_id`, `_ohm_relation_id`, `_geometry_periods[]`.

- [ ] **9.3 Import into the database**

```bash
# Copy JSONL into the container
docker compose -f docker/docker-compose.yml cp output/ohm_borders_smoke.jsonl app:/var/www/html/storage/app/ohm_borders_smoke.jsonl

# Import
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders storage/app/ohm_borders_smoke.jsonl --sync
```

Expected: command completes, prints `Dispatched: N | Skipped malformed: 0`.

- [ ] **9.4 Verify DB state**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "
echo 'Entities: ' . App\Models\Entity::query()->where('verification_status', 'ohm_draft')->count();
echo PHP_EOL;
echo 'GeoRefs: ' . App\Models\EntityGeoRef::query()->where('provider', 'ohm')->count();
echo PHP_EOL;
echo 'GeometryPeriods: ' . App\Models\GeometryPeriod::query()->where('provenance_mode', 'ohm_import')->count();
"
```

Expected: all three counts are > 0.

- [ ] **9.5 Re-run import — verify idempotency**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders storage/app/ohm_borders_smoke.jsonl --sync
```

Expected: entity count unchanged, no duplicates in `geometry_periods`.

- [ ] **9.6 Commit final verification note**

```bash
git add output/.gitkeep  # ensure output dir is tracked if not yet
git commit -m "chore: verified OHM bulk border ingestion end-to-end"
```

---

## Dependency Notes

- `shapely>=2.0.0` must be installed in the Python environment before running the pipeline. If running inside Docker, rebuild the pipeline container or install inline: `pip install shapely`.
- The OHM Overpass API is public but has rate limits. The global query (`[timeout:1800]`) may time out on the public instance. If it does, shard by continent bbox (see cookbook §4.3) and union the JSONL files.
- `provenance_mode='ohm_import'` added as a literal string in `GeometryPeriod::create()` — verify this column is a text column in the migration (not an enum) before running Task 7. If it is an enum, add `ohm_import` in a separate migration first.
