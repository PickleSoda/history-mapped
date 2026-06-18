# Plan 04 - Entity Data Model

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](../../plans/STATUS.md).

> Retroactive plan doc — implementation was completed before this document was written.

## Goal

Implement the full entity data model in PostgreSQL with PostGIS spatial support, pgvector embeddings, and all 30 entity types from the Entity Specification v2.1.

## Scope

- Create PostgreSQL enum types mirroring all application-wide enums from the entity spec (sections 2.1–2.14).
- Build the `entities` table using Single Table Inheritance (STI): one table, 30 entity types, type-specific data in JSONB `attributes`.
- Add PostGIS geometry columns (`geom`, `territory_geom`) with GIST indexes and custom Blueprint macros (no external spatial package — Laravel 13 compatibility).
- Add pgvector `embedding` column with HNSW index for cosine similarity search.
- Create the `relationships` table for inter-entity links with temporal bounds.
- Create the `sources` table for provenance tracking with reliability tiers.
- Create 10 reference tables (`ref_historical_periods`, `ref_geographic_regions`, `ref_historiographical_schools`, `ref_calendar_systems`, `ref_era_date_lookup`, `ref_writing_systems`, `ref_religious_traditions`, `ref_measurement_units`, `ref_language_families`, `ref_source_type_definitions`).
- Build Eloquent models for all tables with proper casts, relationships, and scopes.
- Mirror all PostgreSQL enums as PHP string-backed enums with `declare(strict_types=1)`.

## Deliverables

### Infrastructure
- `PostgisServiceProvider` with `Blueprint::macro('geometry', ...)` and `Blueprint::macro('geography', ...)` for plain geometry type support (no typmod per PostGIS best practices).
- `GeoJson` Eloquent cast for transparent WKB hex to GeoJSON conversion using `ST_AsGeoJSON` / `ST_GeomFromGeoJSON` with SRID 4326.

### PHP Enums (44 files)
- 11 core system enums: `EntityGroup`, `EntityType`, `VerificationStatus`, `ConfidenceLevel`, `ReliabilityTier`, `DateResolutionMethod`, `DurationType`, `LocationResolutionMethod`, `GeometryType`, `IconClass`, `RelationshipType` (76 values).
- 33 domain-specific enums covering political, military, place, economy, event, society, culture, person, and display domains.

### Migrations (5 files)
1. PostgreSQL enum type creation with idempotent `down()` guard for `migrate:fresh`.
2. `entities` table with 13 indexes (2 GIST, 1 HNSW, 3 GIN, 1 GIN tsvector, 4 B-tree, composite temporal, unique wikidata).
3. `relationships` table with UUID PK and CASCADE deletes.
4. `sources` table with content_hash unique index.
5. 10 reference tables with hierarchical self-references, PostGIS geometry on `ref_geographic_regions`, and GIN index on `ref_era_date_lookup.search_variants`.

### Eloquent Models (13 files)
- `Entity` — UUID PK, `HasNeighbors` (pgvector), `GeoJson` cast, 10 enum casts, 7 relationships, 5 query scopes (`ofType`, `ofGroup`, `verified`, `inBbox`, `inTimeRange`).
- `EntityRelationship` — UUID PK, enum casts, source/target entity relationships.
- `Source` — UUID PK, `ReliabilityTier` cast.
- 10 reference models with `$guarded = []`, `$timestamps = false`, self-referential relationships for hierarchical tables.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| STI over polymorphic tables | 30 entity types share ~35 base fields; type-specific data in JSONB `attributes` avoids 30-table join hell. Matches entity spec section 3. |
| Plain `geometry` (no typmod) | PostGIS skill guidelines: avoids ST_Multi/ST_SetSRID clutter. SRID 4326 set at input time in the GeoJson cast. |
| Custom PostGIS macros over `eloquent-spatial` | `matanyadaev/laravel-eloquent-spatial` does not support Laravel 13. Manual Blueprint macros are trivial. |
| PG enums + PHP backed enums | Database-level validation plus Laravel auto-casting. Enum migration calls `$this->down()` at start of `up()` to handle `migrate:fresh` (which drops tables but not PG types). |
| HNSW over IVFFlat for vector index | Better recall at query time; acceptable build time for our dataset scale. |
| `increments()` over `serial()` | `tpetry/laravel-postgresql-enhanced` overrides Blueprint and doesn't implement `serial()`. |
| Self-referencing FKs in separate `Schema::table()` | PostgreSQL cannot validate self-referencing FKs within `CREATE TABLE` when the PK doesn't exist yet. |
| `reviewer_id` as `unsignedBigInteger` | Matches `users.id` which is `$table->id()` (bigint), not UUID. |

## Verification

- `php artisan migrate:fresh --force` passes cleanly inside Docker app container.
- All 5 migrations apply without error.
- All PG enum types, indexes (GIST, HNSW, GIN, B-tree), and foreign keys created correctly.

## Deferred

- Seeding reference tables with data from `docs/implementation-docs/reference_tables.md`.
- Entity API (CRUD actions, DTOs, controllers, routes).
- Scramble OpenAPI auto-documentation wiring.
- Entity factory definitions for testing.
