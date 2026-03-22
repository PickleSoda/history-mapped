# 07 — Geoshape Territory Auto-Population

## Objective

Automatically populate `territory_geom` for entities when Wikidata provides geoshape data (`P3896`), without requiring manual map editing during pipeline imports.

## Problem Addressed

Before this change:

- Point geometry (`geom`) could be populated from coordinate data (`P625`)
- Territory geometry (`territory_geom`) was usually empty unless manually authored
- Some entities already had Wikidata geoshapes, but the pipeline did not resolve them into GeoJSON

This plan implemented an automatic resolver from Wikidata geoshape references to import-ready GeoJSON geometry.

## What Was Implemented

### 1) New Commons geoshape resolver

A new module was added:

- `pipeline/scraper/geoshape.py`

Responsibilities:

- Reads Wikidata geoshape references of the form `Data:*.map`
- Fetches Commons map JSON via:
  - `https://commons.wikimedia.org/w/index.php?title=Data:...&action=raw`
- Parses the Commons payload and normalizes `data` into GeoJSON geometry
- Handles multi-feature map files by merging homogeneous geometry types:
  - polygons → `MultiPolygon`
  - lines → `MultiLineString`
  - points → `MultiPoint`
  - mixed types → `GeometryCollection`
- Caches resolved geometries in-memory per run
- Uses rate limiting and pipeline User-Agent

### 2) Wikidata scraper integration

Updated:

- `pipeline/scraper/wikidata.py`

Changes:

- Added `P3896` to baseline property enrichment set
- Ensured baseline property enrichment always runs (not only when per-type config has `property_queries`)
- Added post-enrichment geoshape step:
  - Extracts geoshape title from enriched `P3896` values
  - Resolves geometry through `GeoshapeResolver`
  - Writes fields into raw item:
    - `geoshape` (string title, e.g., `Data:NewYork.map`)
    - `territory_geojson` (GeoJSON geometry object)

### 3) Topic graph-walk integration

Updated:

- `pipeline/scraper/topic.py`

Changes:

- Extracts `P3896` directly from entity claims in topic-walk mode
- Resolves geoshape via shared `GeoshapeResolver`
- Emits `geoshape` and `territory_geojson` in topic raw items

This keeps topic-based ingestion behavior aligned with type-based scraping.

### 4) Mapper passthrough to import payload

Updated:

- `pipeline/mapper/entity_mapper.py`

Changes:

- Passes `territory_geojson` through to mapped entity output when present

Result:

- Laravel import receives `territory_geojson`
- Existing `CreateEntityAction` already writes it to PostGIS `territory_geom` via `ST_GeomFromGeoJSON`

### 5) Config and env updates

Updated:

- `pipeline/config.py`
- `pipeline/.env.example`

Added setting:

- `COMMONS_REQUESTS_PER_MINUTE` (default `30`)

### 6) Pipeline documentation update

Updated:

- `pipeline/README.md`

Added notes about:

- Automatic `P3896` geoshape resolution
- Commons map fetch and conversion into `territory_geom`

## Validation Performed

### Syntax and diagnostics

- Python compilation succeeded for modified pipeline modules
- Editor diagnostics reported no errors in modified files

### Live endpoint verification

Validated Commons endpoint behavior with a real map page:

- `Data:NewYork.map`
- `action=raw` response includes `data.type = FeatureCollection`
- Feature data is parseable and convertible to GeoJSON geometry

## Current Behavior Summary

When an entity has Wikidata `P3896`:

1. Pipeline extracts map title (`Data:*.map`)
2. Commons JSON is fetched and parsed
3. Geometry is normalized to a GeoJSON geometry object
4. `territory_geojson` is included in pipeline output
5. Laravel import persists it into `territory_geom`

If no valid geoshape is present or resolution fails:

- Import proceeds normally
- `territory_geom` remains null
- No hard failure is introduced in pipeline flow

## Scope Notes and Tradeoffs

- This implementation intentionally resolves only Commons `Data:*.map` geoshapes from `P3896`
- It does not attempt topology repair/simplification beyond basic normalization
- Mixed geometry sets are preserved as `GeometryCollection` for correctness

## Potential Follow-Ups

1. Restrict territory auto-population to selected entity types (polities/regions) if needed
2. Add optional geometry simplification for very large map data
3. Add lightweight metrics (resolved/skipped/error counts) in CLI output
4. Add snapshot support if temporal territory variants are needed later
