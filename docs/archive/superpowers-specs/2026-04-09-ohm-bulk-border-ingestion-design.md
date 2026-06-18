# OHM Bulk Border Ingestion — Design Spec

**Date:** 2026-04-09  
**Status:** Approved — proceeding to implementation plan

---

## Problem

history-mapped's existing geo-resolution flow matches individual entities to OHM features one at a time during scraping. For polities, the more valuable starting point is the opposite direction: pull *everything* OHM has as sovereign-state boundaries (`admin_level=2`), use the `wikidata` tag embedded in each OHM relation to fetch entity metadata in bulk, and seed the database from that foundation rather than from Wikidata SPARQL queries alone.

This gives us:
- All borders OHM has ever mapped, with dates and geometry stages, in one sweep
- Wikidata metadata keyed off the OHM `wikidata` tag (authoritative cross-link)
- `entity_geo_refs` rows with exact OHM relation IDs for reverse-lookup click resolution
- `geometry_periods` rows per chronology stage so the timeline viewer renders actual historic borders

---

## Scope

**In scope:**
- OHM `boundary=administrative` + `admin_level=2` relations worldwide (Overpass via `out geom`)
- For each relation that has a `wikidata` tag: SPARQL batch-fetch of entity metadata
- For each chronology relation: one `_geometry_periods[]` entry per dated member stage
- New Python module `pipeline/ohm_borders/`
- New Laravel command `pipeline:import-borders`
- New Laravel job `ImportBorderEntityJob`

**Out of scope:**
- `admin_level` > 2 (cities, provinces) — deferred
- Inferred boundary generation (plan 14)
- Writing data back to OHM
- Frontend/UI changes — existing OHM viewer consumes `geometry_periods` already

---

## Architecture

```
[Overpass API — OHM]
    │  POST /api/interpreter
    │  relation["boundary"="administrative"]["admin_level"="2"]
    │  out geom;
    ▼
pipeline/ohm_borders/fetcher.py
    │  parse elements array
    │  separate plain boundary relations from type=chronology super-relations
    ▼
pipeline/ohm_borders/enricher.py
    │  collect all wikidata QIDs from tags
    │  SPARQL VALUES batch (≤50 QIDs) → name / aliases / dates / entity_type
    ▼
pipeline/ohm_borders/mapper.py
    │  per OHM relation → build JSONL record
    │  chronology: N member relations → _geometry_periods[]
    │  standalone: single stage → _geometry_periods[] with 1 item
    ▼
output/ohm_borders.jsonl  (one record per sovereign-state polity found)
    │
    ▼
php artisan pipeline:import-borders <file>
    │  per record → ImportBorderEntityJob (sync or queued)
    │     CreateEntityAction (or UpdateEntityAction if wikidata_id exists)
    │     CreateEntityGeoRefAction  (provider=ohm, external_type=relation)
    │     HydrateEntityGeometryFromGeoRefAction  (base entity.geom/territory_geom)
    │     per _geometry_period:
    │       GeometryPeriod::create (start_year, end_year, territory_geom, geo_ref_id)
    ▼
[Canonical DB]
  entities (verification_status=ohm_draft)
  entity_geo_refs (provider=ohm, is_active=true, match_role=primary)
  geometry_periods (period_type=territory, provenance_mode=ohm_import)
```

---

## JSONL Schema Extension

All existing entity JSONL fields are preserved. Two new top-level keys are added:

```jsonc
{
  // ... all existing entity fields (name, entity_type, wikidata_id, etc.) ...

  "_ohm_relation_id": "2790811",        // root OHM relation (or chronology ID)

  "_geometry_periods": [
    {
      "ohm_relation_id": "2790811",     // the specific stage relation ID
      "external_type": "relation",
      "start_year": 1908,               // null if start_date absent
      "end_year": 1946,                 // null if end_date absent
      "start_date": "1908-10-05",       // raw OHM string, may be partial
      "end_date": "1946-09-15",
      "geojson": { "type": "MultiPolygon", "coordinates": [...] },
      "label": "Kingdom of Bulgaria (1908–1946)",
      "external_tags": { "name": "Българско царство", "admin_level": "2", ... }
    }
  ]
}
```

---

## Key Design Decisions

### 1. Python-side geometry assembly
OHM `out geom` inlines member-way coordinates in the response. Member ways must be stitched into closed rings to form polygons. Rather than implement ring-stitching in Python, we use `shapely` (already a transitive dep candidate) with a simple greedy-chain algorithm, or fall back to emitting the raw coordinate arrays tagged as `geom_raw` if assembly fails. Any relation whose geometry cannot be assembled is logged and skipped cleanly.

### 2. Chronology relations
When the fetcher encounters a `type=chronology` super-relation, it follows member refs to the individual boundary stages (each with their own `start_date`/`end_date`). Each stage becomes one `_geometry_periods` entry. The chronology relation's own `wikidata` tag and `name` tag become the canonical entity identity.

When a boundary relation has no parent chronology, it maps to a single `_geometry_periods` entry. `start_year` and `end_year` come from the relation's own `start_date`/`end_date` tags; if absent, they remain `null` and the period covers the full entity lifespan.

### 3. Wikidata QIDs without a hit
OHM relations without a `wikidata` tag still produce a JSONL record; the `wikidata_id` field is null and the entity name comes from the OHM `name:en` or `name` tag. Enrichment is skipped for these. They are still imported as `entity_type=political_entity` with `verification_status=ohm_draft`.

### 4. Laravel import is idempotent
`ImportBorderEntityJob` first looks up an existing entity by `wikidata_id` (or by OHM relation ID in `entity_geo_refs`). If found and `--force` is not set, it skips the entity creation and only upserts `geometry_periods` for stages that don't yet exist (checked by `entity_id + start_year + end_year + geo_ref_id`).

### 5. Verification status
Imported entities are set to `verification_status=ohm_draft` (a new value added to the existing enum), not `pipeline_draft`. This makes bulk imports visually distinguishable in admin views.

### 6. Date parsing
OHM dates are ISO 8601 with support for partial dates and BCE negative years. The Python mapper normalises to a signed integer `start_year`/`end_year` using rule: partial `start_date` → floor year, partial `end_date` → ceiling year. The `edtf` library is already in scope as an optional dep; if not available, fallback to simple regex year extraction.

---

## Affected Files

### New — Python
| File | Purpose |
|---|---|
| `pipeline/ohm_borders/__init__.py` | Package marker |
| `pipeline/ohm_borders/fetcher.py` | Overpass query + response parser |
| `pipeline/ohm_borders/enricher.py` | Wikidata SPARQL batch enrichment |
| `pipeline/ohm_borders/mapper.py` | OHM relation → JSONL record + `_geometry_periods` |
| `pipeline/ohm_borders/date_parser.py` | OHM date → signed int year |

### Modified — Python
| File | Change |
|---|---|
| `pipeline/__main__.py` | Add `borders` CLI command |
| `pipeline/requirements.txt` | Add `shapely` (geometry assembly) |

### New — Laravel
| File | Purpose |
|---|---|
| `api/app/Console/Commands/ImportBordersCommand.php` | `pipeline:import-borders` artisan command |
| `api/app/Jobs/ImportBorderEntityJob.php` | Per-record entity + georef + geometry-periods import |

### Modified — Laravel
| File | Change |
|---|---|
| `api/database/migrations/XXXX_add_ohm_draft_to_verification_status.php` | Add `ohm_draft` to enum |
| `api/app/Enums/VerificationStatus.php` | Add `OhmDraft = 'ohm_draft'` case |

### New — Tests
| File | Covers |
|---|---|
| `pipeline/tests/test_ohm_borders_date_parser.py` | BCE/partial/full date → year int |
| `pipeline/tests/test_ohm_borders_mapper.py` | Standalone + chronology → JSONL |
| `api/tests/Feature/Feature/ImportBordersCommandTest.php` | Entity creation, georef, geometry periods |

---

## Success Criteria

1. `python -m pipeline borders --output output/ohm_borders.jsonl` completes globally without crashing on any relation format.
2. `php artisan pipeline:import-borders output/ohm_borders.jsonl --sync` imports all records, creates `entity_geo_refs` with `provider=ohm`, and creates at least one `geometry_period` per polity that had OHM geometry.
3. Re-running the command with existing data skips creation and does not create duplicates.
4. The OHM map viewer for an entity whose border was ingested shows the correct dated territory polygon.
