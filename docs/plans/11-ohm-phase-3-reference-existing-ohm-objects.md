# Phase 3 — Reference Existing OHM Objects Instead of Re-Creating Geometry

## Objective

Allow entities/snapshots to reference existing OHM objects (node/way/relation), automatically attach these references during pipeline ingestion when possible, and support deterministic map-click resolution back to a WikiGlobe entity.

## Scope

- Data model for OHM references.
- Pipeline attachment flow (Wikidata seed -> OHM match -> fallback -> unresolved).
- API endpoints for attach/list/remove references.
- API endpoint for click resolution by OHM feature identity + date.
- Rendering OHM-referenced objects in map viewer/editor.
- Integrity constraints ensuring canonical georef ownership and uniqueness.

## Out of Scope

- Direct writeback/contribution to OHM API.

## Deliverables

1. New persistence model for OHM references.
2. OHM lookup/fetch service integration.
3. Pipeline auto-attach logic for entity georefs.
4. UI for selecting and attaching OHM objects.
5. Viewer support for rendering referenced OHM geometries with timeframe filtering.
6. Deterministic click-resolution path (`OHM feature -> entity -> date-scoped geometry`).

## Proposed Data Model

- `entity_geo_refs`
  - `geo_ref_id` (uuid)
  - `entity_id` (uuid, required)
  - `provider` (`ohm | wikidata | geonames | pleiades | custom`)
  - `external_type` (`node | way | relation | feature | qid`)
  - `external_id` (text)
  - `match_role` (`primary | candidate | fallback | rejected`)
  - `retrieval_method` (`overpass | nominatim | rest | manual`)
  - `temporal_start` / `temporal_end` (text)
  - `temporal_start_year` / `temporal_end_year` (integer, normalized)
  - `external_tags` (jsonb)
  - `source_meta` (jsonb)
  - `match_score` (numeric)
  - `is_active` (boolean)
  - timestamps
- `entities.primary_geo_ref_id` (uuid, nullable canonical georef pointer)
- `geometry_snapshots.geo_ref_id` (uuid, nullable provenance link)

### Data integrity invariants

- `entities.primary_geo_ref_id` must reference a `entity_geo_refs` row owned by the same `entity_id`.
- Max one active primary georef row per entity (`match_role='primary'` + `is_active=true`).
- Lookup indexes must support fast reverse resolution on `(provider, external_type, external_id, is_active)`.

## Implementation Tasks

### 3.1 Schema + model layer

- Migration + model + relations from Entity/Snapshot.
- Validation for mutually exclusive entity/snapshot association where needed.
- Add/verify constraints and indexes for ownership/uniqueness/lookup performance.

### 3.2 Pipeline auto-attach flow

- In Stage 3 georesolution, attempt OHM match first (Nominatim -> Overpass/REST).
- If OHM match exists:
  - create `entity_geo_refs` row with `provider='ohm'`, set `match_role='primary'` when canonical;
  - set `entities.primary_geo_ref_id`;
  - hydrate `geom`/`territory_geom` and optional `geometry_snapshots.geo_ref_id`.
- If OHM fails, attempt fallback dataset/manual source and mark `match_role='fallback'`.
- If fallback fails, leave geometry null and mark unresolved status.

### 3.3 OHM data retrieval service

- Implement OHM client for:
  - REST API element fetch
  - relation `/full` support
  - optional Overpass query helper
- Normalize response to GeoJSON for viewer consumption.

### 3.4 API endpoints

- `POST /entities/{id}/geography-references`
- `GET /entities/{id}/geography-references`
- `DELETE /entities/{id}/geography-references/{ref}`
- Snapshot-level equivalents if required.
- Add click-resolution endpoint/action:
  - `POST /map/resolve-ohm-feature`
  - input: `provider`, `external_type`, `external_id`, `target_year`
  - output: `entity`, resolved geometry, matched georef id, resolution source.

### 3.5 UI workflow

- "Reference from OHM" action in editor.
- Search/lookup by ID and optional name workflow.
- Attach selected OHM object as entity/snapshot geometry source.

### 3.6 Rendering precedence rules

- Define precedence when both local geometry and OHM references exist.
- Support toggling visibility between local vs referenced source.
- Date-scoped precedence:
  1. matching `geometry_snapshots` for selected year;
  2. else base entity geometry.

### 3.7 Deterministic reverse lookup + tests

- Implement service query path: `(provider, external_type, external_id, target_year) -> entity`.
- Tie-breakers:
  1. active primary georef,
  2. highest match score,
  3. latest update, deterministic id fallback.
- Add tests for:
  - successful OHM relation click resolution,
  - snapshot vs base geometry fallback,
  - inactive georef exclusion,
  - ownership constraint violation rejection.

## Dependencies

- Phase 1 timeframe integration.
- Phase 2 viewer interaction structure.

## Risks

- OHM API latency/rate limits.
- Complex relation geometries requiring robust normalization.

## Mitigations

- Cache fetched OHM geometries in app layer (short TTL + invalidation strategy).
- Progressive rendering for large relations.

## Exit Criteria

- User can attach existing OHM object to entity/snapshot manually.
- Pipeline auto-attaches OHM references where a deterministic match exists.
- Clicking OHM-rendered Rome (or equivalent) resolves to one deterministic entity for a chosen date.
- Referenced geometry renders on map without local redrawing.
- Reference metadata persists, is queryable, and is integrity-constrained.

## Status

- Planned
