# Phase 3 — Reference Existing OHM Objects Instead of Re-Creating Geometry

## Objective

Allow entities/snapshots to reference existing OHM objects (node/way/relation), automatically attach these references during pipeline ingestion when possible, and support deterministic map-click resolution back to a WikiGlobe entity.

## Scope

- Data model for OHM references.
- Pipeline attachment flow (Wikidata seed -> OHM match -> fallback -> unresolved).
- API endpoints for attach/list/remove references.
- API endpoint for click resolution by OHM feature identity + date.
- Local geometry hydration from attached OHM references.
- Integrity constraints ensuring canonical georef ownership and uniqueness.

## Out of Scope

- Direct writeback/contribution to OHM API.
- Rendering directly from `entity_geo_refs`.
- Changing the existing map hot path to read geometry from georef records.

## Deliverables

1. New persistence model for OHM references.
2. OHM lookup/fetch service integration.
3. Pipeline auto-attach logic for entity georefs.
4. UI for selecting and attaching OHM objects.
5. Deterministic click-resolution path (`OHM feature -> entity -> date-scoped geometry`).
6. Local PostGIS hydration path so attached OHM references can populate `entities` / `geometry_snapshots` without changing renderer queries.

## Current Implementation Slice

This phase is being implemented backend-first with a strict separation between
reference metadata and render geometry.

- `entity_geo_refs` is a provenance and reverse-lookup table, not a render source.
- Map rendering continues to read only from `entities.geom`, `entities.territory_geom`,
  and `geometry_snapshots`.
- When an OHM object is attached and accepted as canonical, its geometry is hydrated
  into the existing local PostGIS columns/tables.
- `geometry_snapshots.geo_ref_id` is a provenance link only.
- Viewer/editor attachment workflows remain part of Phase 3, but follow the backend
  schema/API foundation rather than leading it.

## Recommended Service Boundary

For the current Phase 3 scope, automatic georesolution should be authoritative in the
Python pipeline, with Laravel acting as the persistence and manual-override layer.

- Python pipeline responsibility:
  - scrape and normalize Wikidata/Wikipedia inputs;
  - perform OHM lookup and future fallback/inferred-boundary decisions;
  - emit a canonical `_geo_resolution` manifest in JSONL output;
  - decide whether an entity is `matched`, `no_match`, or `skipped`.
- Laravel import/application responsibility:
  - consume the pipeline's `_geo_resolution` verdict without re-running matching logic;
  - write `entity_geo_refs` and `primary_geo_ref_id`;
  - hydrate local PostGIS geometry from the emitted geometry payload;
  - support manual attach/search/remove workflows for editors.

### Why this is the right split now

- One automatic decision-maker. OHM lookup and fallback policy live in the same place that
  already understands pipeline-scale enrichment, batch processing, and unresolved entities.
- Cleaner fallback evolution. Inferred boundaries and non-OHM fallbacks belong next to the
  pipeline's broader enrichment logic, not split across Python and Laravel.
- Stable importer contract. Laravel no longer needs source-specific matching heuristics in the
  import path; it only persists the canonical verdict.
- Manual flows stay separate. Admin/editor attach flows can continue to use Laravel-side OHM
  services for interactive lookup without becoming the source of truth for automated imports.

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

- In Stage 3 georesolution, the Python pipeline attempts OHM match first and later fallback engines.
- If OHM match exists, the pipeline emits `_geo_resolution.status='matched'` with the canonical
  `geo_ref`, geometry payload, and provenance metadata.
- Laravel import consumes that manifest by:
  - creating the `entity_geo_refs` row;
  - setting `entities.primary_geo_ref_id`;
  - hydrating `geom`/`territory_geom` into local PostGIS storage.
- If OHM fails, the pipeline emits `no_match` for now and can later emit fallback matches.
- If resolution is intentionally skipped, the pipeline emits `skipped`.

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
- Snapshot-level attach is currently supported via `POST/PUT /entities/{id}/geometry-snapshots` using nested `geography_reference` input; dedicated snapshot georef endpoints remain deferred.
- Add click-resolution endpoint/action:
  - `POST /map/resolve-ohm-feature`
  - input: `provider`, `external_type`, `external_id`, `target_year`
  - output: `entity`, resolved geometry, matched georef id, resolution source.

### 3.5 UI workflow

- Planned as a follow-on slice within Phase 3 after the backend schema/API foundation lands.
- "Reference from OHM" action in editor.
- Search/lookup by ID and optional name workflow.
- Attach selected OHM object as entity/snapshot geometry source via the new backend endpoints.
- Manual attach/list/remove remains available through API during backend-first implementation.

### 3.6 Rendering precedence rules

- For the current slice, rendering remains unchanged and reads only from local geometry.
- Date-scoped precedence remains:
  1. matching `geometry_snapshots` for selected year;
  2. else base entity geometry.
- Future viewer work may expose source toggles, but that is deferred.

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

- User can attach existing OHM object to entity manually via API.
- Pipeline auto-attaches OHM references where a deterministic match exists.
- Clicking OHM-rendered Rome (or equivalent) resolves to one deterministic entity for a chosen date.
- Attached OHM references can hydrate local geometry without changing the map render query path.
- Reference metadata persists, is queryable, and is integrity-constrained.

## Status

- In progress
- Where we stand now:
  1. Schema + model layer
    - Done.
    - `entity_geo_refs`, ownership constraints, the primary pointer, and snapshot
     provenance links are in place.
  2. Pipeline auto-attach flow
    - Partially done.
    - Deterministic OHM matching now runs in the Python pipeline and emits `_geo_resolution`.
    - Laravel import consumes the manifest and hydrates local geometry.
    - Exact normalized-name matching is enforced.
    - Fallback source flow is still not implemented.
  3. OHM retrieval service
    - Partially done.
    - Nominatim lookup and name search are implemented.
    - REST `/full`, Overpass helpers, and caching are still missing.
  4. API endpoints
    - Mostly done for backend foundations.
    - Entity georef CRUD is done.
    - Reverse-resolution endpoint is done.
    - Snapshot attach is supported through snapshot create/update payloads.
    - Dedicated snapshot georef endpoints are still deferred.
  5. UI workflow
    - Not started as a product-integrated workflow.
    - This is now the largest remaining user-facing gap in Phase 3.
  6. Rendering precedence rules
    - Done for current scope.
    - Rendering still reads only local PostGIS geometry.
  7. Deterministic reverse lookup + tests
    - Done for the current backend scope.
    - Reverse resolution, integrity constraints, entity attach, snapshot attach,
     lifecycle cleanup, and deterministic pipeline matching are covered.
- Completed:
  - `entity_geo_refs` schema, constraints, enums, and ownership invariants
  - Entity georef CRUD API
  - Deterministic reverse lookup endpoint (`/map/resolve-ohm-feature`)
  - Attach-time OHM lookup and local entity geometry hydration
  - Stage 3 pipeline `_geo_resolution` manifest import for deterministic OHM matches
  - Snapshot attach via nested `geography_reference` on snapshot create/update
  - Snapshot georef lifecycle cleanup for delete and replacement of orphan candidate refs
- Remaining:
  - OHM retrieval expansion beyond current Nominatim lookup/search path (REST `/full`, Overpass helpers, caching)
  - UI/editor workflows for entity and snapshot OHM attach/search/remove
  - Final viewer-side integration for click-driven workflows and attachment UX

## Recommended Parallel Workstreams

While the UI/editor slice is being built, the following backend work can proceed safely in
parallel without forcing schema churn.

1. OHM retrieval hardening in Python
  - Add REST element expansion, relation `/full`, optional Overpass helpers, and short-TTL caching.
  - This improves pipeline resolution coverage before import.
2. Alias-aware deterministic matching
  - Extend the current exact normalized-name matcher with aliases, Wikidata labels, and curated alternates.
  - Keep the matching policy deterministic and conservative.
3. Fallback-source contract
  - Define and implement the first non-OHM fallback path so unresolved imports can become explicit `fallback` refs.
  - Laravel import already has a stable manifest contract to consume these later.
4. Viewer click-through integration
  - Wire the existing reverse-resolution endpoint into the viewer/editor interaction layer.
  - This remains separate from the import-side manifest flow.
5. Operational hardening
  - Add caching observability, rate-limit handling, and failure telemetry around pipeline OHM retrieval.

## Recommended Next Step

Primary recommendation: keep the UI/editor OHM attach workflow as the lead slice, while
running OHM retrieval hardening in Laravel in parallel.

Reason:

- The backend contract is already stable enough to support the editor/viewer flow.
- UI integration is the biggest remaining product gap.
- Retrieval hardening is the best parallel backend track because it improves both manual
  attach UX and pipeline attach coverage without changing the Phase 3 data model.
