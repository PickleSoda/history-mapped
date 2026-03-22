# Phase 3 — Reference Existing OHM Objects Instead of Re-Creating Geometry

## Objective
Allow entities/snapshots to reference existing OHM objects (node/way/relation) so users can reuse historical boundaries and places rather than redrawing them.

## Scope
- Data model for OHM references.
- API endpoints for attach/list/remove references.
- Rendering OHM-referenced objects in map viewer/editor.

## Out of Scope
- Direct writeback/contribution to OHM API.

## Deliverables
1. New persistence model for OHM references.
2. OHM lookup/fetch service integration.
3. UI for selecting and attaching OHM objects.
4. Viewer support for rendering referenced OHM geometries with timeframe filtering.

## Proposed Data Model
- `entity_geography_references`
  - `id` (uuid)
  - `entity_id` (nullable when snapshot-level)
  - `snapshot_id` (nullable when entity-level)
  - `ohm_type` (`node | way | relation`)
  - `ohm_id` (bigint/string)
  - `role` (`primary_boundary | center | route | related`)
  - `temporal_start` / `temporal_end` (nullable)
  - `metadata` (jsonb)
  - timestamps

## Implementation Tasks

### 3.1 Schema + model layer
- Migration + model + relations from Entity/Snapshot.
- Validation for mutually exclusive entity/snapshot association where needed.

### 3.2 OHM data retrieval service
- Implement OHM client for:
  - REST API element fetch
  - relation `/full` support
  - optional Overpass query helper
- Normalize response to GeoJSON for viewer consumption.

### 3.3 API endpoints
- `POST /entities/{id}/geography-references`
- `GET /entities/{id}/geography-references`
- `DELETE /entities/{id}/geography-references/{ref}`
- Snapshot-level equivalents if required.

### 3.4 UI workflow
- "Reference from OHM" action in editor.
- Search/lookup by ID and optional name workflow.
- Attach selected OHM object as entity/snapshot geometry source.

### 3.5 Rendering precedence rules
- Define precedence when both local geometry and OHM references exist.
- Support toggling visibility between local vs referenced source.

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
- User can attach existing OHM object to entity/snapshot.
- Referenced geometry renders on map without local redrawing.
- Reference metadata persists and is queryable.

## Status
- Planned
