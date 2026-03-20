# Attributes Storage & Geometry Snapshots — Implementation Plan

**Version 1.0 — March 2026**
**Status:** Planned
**Companion to:** Entity Specification v2.1, Web Implementation Architecture

---

## Table of Contents

1. [Context and Problem Statement](#1-context-and-problem-statement)
2. [Decision: JSONB for Type-Specific Fields](#2-decision-jsonb-for-type-specific-fields)
3. [Decision: Dedicated Table for Time-Varying Geometries](#3-decision-dedicated-table-for-time-varying-geometries)
4. [Schema Design — `geometry_snapshots`](#4-schema-design--geometry_snapshots)
5. [Expression Indexes on JSONB Attributes](#5-expression-indexes-on-jsonb-attributes)
6. [Query Patterns](#6-query-patterns)
7. [API Surface](#7-api-surface)
8. [Laravel Implementation Checklist](#8-laravel-implementation-checklist)
9. [Migration Strategy](#9-migration-strategy)
10. [Testing Plan](#10-testing-plan)

---

## 1. Context and Problem Statement

The entity specification defines 30 entity types across 5 groups, each with type-specific fields (Section 4 of `entity_specification.md`). The current schema stores all type-specific data in a single JSONB `attributes` column on the `entities` table. Two questions need answering:

1. **Should the ~200 type-specific fields remain in JSONB, or move to dedicated sub-tables?**
2. **How do we model time-varying PostGIS geometries** (e.g., empire borders changing century by century)?

### Current State

- `entities` table has a `jsonb attributes DEFAULT '{}'` column with a GIN index
- All 30 entity types use single-table inheritance via `entity_type` / `entity_group` enum columns
- The map hot path (`/api/v1/map/entities`) only queries base columns: `entity_id`, `name`, `entity_type`, `entity_group`, `temporal_start_year`, `temporal_end_year`, `impact_score`, `geom`, `icon_class`, `entity_color`, `display_priority`
- Type-specific attributes are **never** queried on the map hot path — they are loaded only on entity detail views
- The `geom` and `territory_geom` PostGIS columns store a single static geometry per entity

### Key Constraint

Empire borders, trade routes, city control, and migration paths change over time. The current schema cannot represent the Roman Empire's territory in 117 CE vs. 395 CE without creating separate entities for each era — which breaks the single-entity identity model.

---

## 2. Decision: JSONB for Type-Specific Fields

**All 30 entity type-specific field sets remain in the `attributes` JSONB column.**

### Rationale

| Criterion | JSONB | Sub-Tables (30 tables) |
|-----------|-------|----------------------|
| Map query hot path | Not involved — zero cost | Not involved — zero cost |
| Detail view load | Single row read, decode JSON | JOIN to type-specific table |
| Schema evolution | Add/rename keys without DDL | ALTER TABLE per change |
| Pipeline ingestion | Single INSERT per entity | INSERT into 2 tables per entity |
| Admin panel CRUD | Generic form builder from JSON schema | Per-type form + model |
| Cross-type search | `attributes @> '{"key": "value"}'::jsonb` | UNION across 30 tables |
| Filtered queries | Expression index on specific keys | Native B-tree on columns |
| Storage overhead | Slight duplication of key names | Normalized, minimal overhead |
| Code complexity | 1 model, 1 table, JSON validation | 30 models, 30 migrations, 30 form requests |

**Bottom line:** Sub-tables only win on filtered queries, and expression indexes close that gap. For a system where 95% of attribute access is "load detail for one entity", JSONB is the clear winner.

### What Goes in `attributes`

Every field listed in Section 4 of the entity specification, organized by entity type. Example for `political_entity`:

```json
{
  "political_subtype": "empire",
  "government_type": "bureaucratic_centralized",
  "government_history": [{"type": "monarchy", "start": -753, "end": -509}],
  "capital_history": [{"city_entity_id": "uuid-here", "start": -753, "end": -509}],
  "population_estimates": [{"value": 55000000, "year": 117, "source": "census"}],
  "territory_area_estimates": [{"km2": 5000000, "year": 117, "source": "estimate"}],
  "official_languages": [{"language_entity_id": "uuid-here", "start": -200, "end": 476}],
  "official_religions": [{"religious_movement_id": "uuid-here", "start": 380, "end": 476}],
  "succession_type": "primogeniture",
  "administrative_divisions": [{"name": "Syria", "type": "province", "entity_id": "uuid-here"}]
}
```

### What Does NOT Go in `attributes`

- **PostGIS geometries** — these need GIST indexes and spatial queries → `geometry_snapshots` table
- **Foreign key references that need referential integrity** — stored as base columns (`parent_entity_id`, `successor_entity_id`) or in the `relationships` table
- **Fields used in the map hot path** — already base columns (`impact_score`, `temporal_start_year`, etc.)

---

## 3. Decision: Dedicated Table for Time-Varying Geometries

**A `geometry_snapshots` table stores versioned PostGIS geometries per entity.**

### Why Not JSONB for Geometries?

- PostGIS `geometry` columns require GIST indexes for spatial queries (`&&`, `ST_DWithin`, etc.)
- GeoJSON stored as JSONB text cannot be spatially indexed
- The map must query "show me all territory polygons that existed in 200 CE within this bounding box" — this requires a spatial + temporal compound query that only works with proper PostGIS columns

### Relationship to Base `geom` / `territory_geom`

The existing `geom` and `territory_geom` columns on the `entities` table remain as the **canonical/default geometry** — typically the best-known or most representative location. The `geometry_snapshots` table stores **temporal variations**:

- **Entity with no snapshots:** Uses `geom` / `territory_geom` as-is (vast majority of entities)
- **Entity with snapshots:** The map queries `geometry_snapshots` filtered by the active year; base `geom` serves as the fallback/centroid

This means the existing map hot path continues to work unchanged for point entities (cities, battles, monuments). Only entities with time-varying territory (empires, trade routes, migration paths) need snapshots.

---

## 4. Schema Design — `geometry_snapshots`

### Table Schema

```sql
CREATE TABLE geometry_snapshots (
    snapshot_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id         UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,

    -- Temporal validity (integer years, same convention as entities table)
    year_start        INTEGER NOT NULL,        -- First year this geometry is valid
    year_end          INTEGER NOT NULL,         -- Last year this geometry is valid

    -- Geometry (at least one must be non-null)
    geom              GEOMETRY,                 -- Point/LineString for this time period
    territory_geom    GEOMETRY,                 -- Polygon/MultiPolygon for this time period

    -- Metadata
    label             TEXT,                     -- e.g. "Roman Empire at greatest extent"
    confidence        confidence_level,         -- high/medium/low/unresolved
    source_citations  JSONB,                    -- [{source_id, page, quote}]
    notes             TEXT,                     -- Editorial notes about this snapshot
    display_priority  INTEGER DEFAULT 0,        -- For overlapping periods

    created_at        TIMESTAMP DEFAULT now(),
    updated_at        TIMESTAMP DEFAULT now(),
    created_by        TEXT
);

-- Indexes
CREATE INDEX gs_entity_id_idx ON geometry_snapshots (entity_id);
CREATE INDEX gs_year_range_idx ON geometry_snapshots (year_start, year_end);
CREATE INDEX gs_entity_year_idx ON geometry_snapshots (entity_id, year_start, year_end);
CREATE INDEX gs_geom_gist_idx ON geometry_snapshots USING GIST (geom);
CREATE INDEX gs_territory_gist_idx ON geometry_snapshots USING GIST (territory_geom);

-- Compound spatial + temporal index for the map hot path
CREATE INDEX gs_territory_year_gist_idx ON geometry_snapshots
    USING GIST (territory_geom)
    WHERE territory_geom IS NOT NULL;

-- Constraint: at least one geometry must be present
ALTER TABLE geometry_snapshots ADD CONSTRAINT gs_has_geometry
    CHECK (geom IS NOT NULL OR territory_geom IS NOT NULL);

-- Constraint: year_start <= year_end
ALTER TABLE geometry_snapshots ADD CONSTRAINT gs_valid_year_range
    CHECK (year_start <= year_end);
```

### Example Data

```
entity: Roman Empire (entity_id: abc-123)
  base geom:           POINT(12.4964 41.9028)  -- Rome (centroid/capital)
  base territory_geom: NULL                      -- too variable to pick one

geometry_snapshots:
  snapshot 1: year_start=-27,  year_end=14,   territory_geom=<Augustan borders polygon>
  snapshot 2: year_start=14,   year_end=117,  territory_geom=<expanding borders polygon>
  snapshot 3: year_start=117,  year_end=117,  territory_geom=<Trajan maximum extent>
  snapshot 4: year_start=117,  year_end=285,  territory_geom=<contracting borders polygon>
  snapshot 5: year_start=285,  year_end=395,  territory_geom=<Diocletian era polygon>
  snapshot 6: year_start=395,  year_end=476,  territory_geom=<Western empire only>
```

### Handling Overlapping Periods

Snapshots may overlap when sources disagree. The `display_priority` column determines which is shown on the map. In the detail panel, all overlapping snapshots can be presented with their `confidence` and `source_citations` for scholarly comparison.

---

## 5. Expression Indexes on JSONB Attributes

For type-specific attribute keys that are commonly used in filter queries (admin panel list views, API filtering), add PostgreSQL expression indexes scoped to the relevant entity type via partial indexes.

### Recommended Indexes (Phase 1)

These cover the most likely filter patterns based on the entity specification:

```sql
-- Political entities: filter by subtype and government type
CREATE INDEX entities_attr_political_subtype_idx
    ON entities ((attributes->>'political_subtype'))
    WHERE entity_type = 'political_entity';

CREATE INDEX entities_attr_government_type_idx
    ON entities ((attributes->>'government_type'))
    WHERE entity_type = 'political_entity';

-- Cities: filter by settlement subtype
CREATE INDEX entities_attr_settlement_subtype_idx
    ON entities ((attributes->>'settlement_subtype'))
    WHERE entity_type = 'city';

-- Military units: filter by unit subtype and composition
CREATE INDEX entities_attr_unit_subtype_idx
    ON entities ((attributes->>'unit_subtype'))
    WHERE entity_type = 'military_unit';

-- Infrastructure: filter by monument subtype
CREATE INDEX entities_attr_monument_subtype_idx
    ON entities ((attributes->>'monument_subtype'))
    WHERE entity_type = 'infrastructure_monument';

-- Wars: filter by war subtype
CREATE INDEX entities_attr_war_subtype_idx
    ON entities ((attributes->>'war_subtype'))
    WHERE entity_type = 'event_war';

-- Battles: filter by outcome
CREATE INDEX entities_attr_battle_outcome_idx
    ON entities ((attributes->>'outcome'))
    WHERE entity_type = 'event_battle';

-- Trade routes: filter by route subtype
CREATE INDEX entities_attr_route_subtype_idx
    ON entities ((attributes->>'route_subtype'))
    WHERE entity_type = 'trade_route';

-- Natural resources: filter by category
CREATE INDEX entities_attr_resource_category_idx
    ON entities ((attributes->>'resource_category'))
    WHERE entity_type = 'natural_resource';

-- Epidemics: filter by subtype and severity
CREATE INDEX entities_attr_epidemic_subtype_idx
    ON entities ((attributes->>'epidemic_subtype'))
    WHERE entity_type = 'epidemic_disease';

-- Persons: filter by gender
CREATE INDEX entities_attr_person_gender_idx
    ON entities ((attributes->>'gender'))
    WHERE entity_type = 'person';
```

### When to Add More

Add expression indexes when:
- An admin panel filter is added for a specific attribute key
- An API endpoint accepts that key as a query parameter
- Query EXPLAIN shows sequential scans on the `attributes` column

Do NOT proactively index every JSONB key — the GIN index on `attributes` already handles ad-hoc containment queries (`@>`). Expression indexes are for equality lookups on high-use columns.

---

## 6. Query Patterns

### 6.1 Map Hot Path — Entities in Viewport at Year

```sql
-- Existing: point entities (unchanged)
SELECT entity_id, name, entity_type, entity_group, impact_score,
       ST_AsGeoJSON(geom)::jsonb AS geojson
FROM entities
WHERE geom && ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326)
  AND temporal_start_year <= :year
  AND temporal_end_year >= :year
ORDER BY impact_score DESC NULLS LAST
LIMIT :limit;

-- New: territory polygons at a given year
SELECT gs.snapshot_id, gs.entity_id, e.name, e.entity_type, e.entity_group,
       e.impact_score, gs.label, gs.confidence,
       ST_AsGeoJSON(gs.territory_geom)::jsonb AS territory_geojson
FROM geometry_snapshots gs
JOIN entities e ON e.entity_id = gs.entity_id
WHERE gs.territory_geom && ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326)
  AND gs.year_start <= :year
  AND gs.year_end >= :year
ORDER BY e.impact_score DESC NULLS LAST, gs.display_priority DESC;
```

### 6.2 Entity Detail — Load All Snapshots

```sql
SELECT snapshot_id, year_start, year_end, label, confidence, notes,
       ST_AsGeoJSON(geom)::jsonb AS geom_geojson,
       ST_AsGeoJSON(territory_geom)::jsonb AS territory_geojson,
       source_citations
FROM geometry_snapshots
WHERE entity_id = :entityId
ORDER BY year_start;
```

### 6.3 Filter by JSONB Attribute (Admin Panel)

```php
// Uses the expression index via EntityBuilder::hasAttribute()
Entity::query()
    ->ofType(EntityType::PoliticalEntity)
    ->hasAttribute('political_subtype', 'empire')
    ->orderByImpact()
    ->paginate(25);
```

### 6.4 Timeline Animation — All Snapshots for Entity

```sql
-- Returns ordered geometry keyframes for client-side interpolation
SELECT year_start, year_end, label,
       ST_AsGeoJSON(territory_geom)::jsonb AS territory_geojson
FROM geometry_snapshots
WHERE entity_id = :entityId
  AND territory_geom IS NOT NULL
ORDER BY year_start;
```

---

## 7. API Surface

### 7.1 Geometry Snapshots Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/entities/{entityId}/geometry-snapshots` | List all snapshots for an entity |
| `GET` | `/api/v1/entities/{entityId}/geometry-snapshots/at/{year}` | Get the snapshot valid at a specific year |
| `POST` | `/api/v1/entities/{entityId}/geometry-snapshots` | Create a new snapshot (admin) |
| `PUT` | `/api/v1/entities/{entityId}/geometry-snapshots/{snapshotId}` | Update a snapshot (admin) |
| `DELETE` | `/api/v1/entities/{entityId}/geometry-snapshots/{snapshotId}` | Delete a snapshot (admin) |

### 7.2 Map Endpoint Extension

The existing `/api/v1/map/entities` endpoint gains an optional `include_territories=true` query parameter. When set, the response includes a `territories` array alongside the existing `entities` array, sourced from `geometry_snapshots`.

### 7.3 Entity Detail Extension

The entity detail response (`GET /api/v1/entities/{entityId}`) includes a `geometry_snapshots_count` field. The full snapshots are lazy-loaded via the dedicated sub-resource endpoint.

---

## 8. Laravel Implementation Checklist

### Migration

- [ ] Create `2026_XX_XX_create_geometry_snapshots_table.php`
  - UUID primary key, entity_id FK with CASCADE delete
  - `year_start` / `year_end` integer columns
  - PostGIS `geom` and `territory_geom` columns
  - Metadata columns: `label`, `confidence`, `source_citations`, `notes`, `display_priority`
  - Timestamps and `created_by`
  - All indexes from Section 4
  - CHECK constraints (has geometry, valid year range)

- [ ] Create `2026_XX_XX_add_jsonb_expression_indexes_to_entities.php`
  - All 11 expression indexes from Section 5

### Models

- [ ] Create `App\Models\GeometrySnapshot`
  - UUID primary key, `geometry_snapshots` table
  - Casts: `geom` → `GeoJson`, `territory_geom` → `GeoJson`, `confidence` → `ConfidenceLevel`, `source_citations` → `json`
  - BelongsTo: `entity()`

- [ ] Update `App\Models\Entity`
  - Add `HasMany` relationship: `geometrySnapshots()`
  - Add `geometrySnapshotAt(int $year)` convenience method

### Builder

- [ ] Create `App\Builders\GeometrySnapshotBuilder`
  - `forEntity(string $entityId)` — filter by entity
  - `atYear(int $year)` — `WHERE year_start <= ? AND year_end >= ?`
  - `inBbox(...)` — spatial bounding box filter on `territory_geom`
  - `withGeoJson()` — select with `ST_AsGeoJSON` conversion
  - `orderChronologically()` — order by `year_start`

- [ ] Update `App\Builders\EntityBuilder`
  - Add `withSnapshotAt(int $year)` — eager-load the matching snapshot
  - Add `withAllSnapshots()` — eager-load all snapshots (for detail view)

### Actions

- [ ] Create `App\Actions\GeometrySnapshot\ListSnapshotsAction`
- [ ] Create `App\Actions\GeometrySnapshot\CreateSnapshotAction`
- [ ] Create `App\Actions\GeometrySnapshot\UpdateSnapshotAction`
- [ ] Create `App\Actions\GeometrySnapshot\DeleteSnapshotAction`

### DTOs

- [ ] Create `App\DTOs\GeometrySnapshotData`
  - Properties: `entityId`, `yearStart`, `yearEnd`, `geom`, `territoryGeom`, `label`, `confidence`, `sourceCitations`, `notes`, `displayPriority`

### HTTP Layer

- [ ] Create `App\Http\Api\V1\Requests\StoreGeometrySnapshotRequest`
- [ ] Create `App\Http\Api\V1\Requests\UpdateGeometrySnapshotRequest`
- [ ] Create `App\Http\Api\V1\Resources\GeometrySnapshotResource`
- [ ] Create `App\Http\Api\V1\Controllers\GeometrySnapshotController`
- [ ] Register routes in `routes/api.php`

### Map Endpoint

- [ ] Update `App\Actions\Entity\MapEntitiesAction` to optionally query `geometry_snapshots` when `include_territories` is requested
- [ ] Update `App\Http\Api\V1\Requests\MapEntitiesRequest` to accept `include_territories` boolean

### Tests

- [ ] `tests/Feature/GeometrySnapshotControllerTest.php` — CRUD operations
- [ ] `tests/Unit/GeometrySnapshotBuilderTest.php` — builder query methods
- [ ] `tests/Feature/MapEntitiesWithTerritoriesTest.php` — map endpoint with snapshots
- [ ] Update `EntityFactory` with `withGeometrySnapshots()` state

---

## 9. Migration Strategy

### Phase 1 — Schema Only (No Data Changes)

1. Run `geometry_snapshots` migration — creates empty table
2. Run expression indexes migration — adds partial indexes to existing `attributes` column
3. Deploy updated code — new model, builder, controller, routes
4. All existing API behavior is unchanged (no snapshots to return)

### Phase 2 — Data Population

1. Manual/pipeline creation of geometry snapshots for high-value entities (Roman Empire, Mongol Empire, Ottoman Empire, etc.)
2. Admin panel UI for drawing territory polygons on a MapLibre map with a time slider
3. Import from external GIS datasets (HGIS, World Historical Gazetteer) where available

### Phase 3 — Map Integration

1. Web client adds territory layer that queries `geometry_snapshots`
2. Time slider changes trigger re-fetch of territory polygons for the active year
3. Territory polygons rendered as filled/stroked map layers below point markers

### Rollback

Both migrations are independently reversible. The `geometry_snapshots` table can be dropped without affecting the `entities` table. Expression indexes can be dropped without affecting data.

---

## 10. Testing Plan

### Unit Tests

- `GeometrySnapshotBuilder::atYear()` returns correct snapshot for overlapping periods
- `GeometrySnapshotBuilder::inBbox()` spatial filtering
- `GeometrySnapshot` model casts work correctly
- Expression indexes are used (EXPLAIN ANALYZE in test)

### Feature Tests

- CRUD lifecycle for geometry snapshots via API
- Map endpoint returns territories when `include_territories=true`
- Map endpoint excludes territories when `include_territories=false` (default)
- Entity detail includes `geometry_snapshots_count`
- Deleting an entity cascades to geometry snapshots

### Edge Cases

- Entity with no snapshots — map falls back to base `geom`/`territory_geom`
- Overlapping snapshot periods — `display_priority` determines winner
- Negative years (BCE) — spatial + temporal compound query works
- Large polygon — performance check with realistic polygon complexity (~1000 vertices)
