# TODO

> For verified per-plan execution status (✅/🟡/⬜ across the whole `plans/` set), see [plans/STATUS.md](plans/STATUS.md). This file tracks finer-grained task items within the programs below.

## OHM Integration Program

### Queue (Execution Order)

1. **Phase 0 — Stabilize Geometry Rendering Pipeline**  
  Plan: `docs/plans/08-ohm-phase-0-stabilize-rendering.md`
2. **Phase 1 — OHM Basemap + Timeframe Filtering**  
  Plan: `docs/plans/09-ohm-phase-1-ohm-basemap-and-timeframe.md`
3. **Phase 2 — Timeline-to-Map Interaction (Snapshots + Relationships)**  
  Plan: `docs/plans/10-ohm-phase-2-timeline-map-interaction.md`
4. **Phase 3 — Reference Existing OHM Objects**  
  Plan: `docs/plans/11-ohm-phase-3-reference-existing-ohm-objects.md`
5. **Phase 4 — OHM iD Editor Integration**  
  Plan: `docs/plans/12-ohm-phase-4-ohm-id-editor-integration.md`
6. **Phase 5 — Change Requests + Contribution Pipeline**  
  Plan: `docs/plans/13-ohm-phase-5-change-requests-and-contribution-pipeline.md`

### Progress Tracker

- [x] **Phase 0** — Stabilize Geometry Rendering Pipeline
- [ ] **Phase 1** — OHM Basemap + Timeframe Filtering _(in progress)_
- [ ] **Phase 2** — Timeline-to-Map Interaction (Snapshots + Relationships)
- [ ] **Phase 3** — Reference Existing OHM Objects
- [ ] **Phase 4** — OHM iD Editor Integration
- [ ] **Phase 5** — Change Requests + Contribution Pipeline

### Current Status

- Program design complete.
- Detailed per-phase plans documented.
- Phase 3 now includes pipeline auto-attach + click-resolution + georef integrity hardening.
- **Phase 0 complete** — 169/169 tests passing. Shared viewer extracted, normalization utility reused throughout, source-readiness lifecycle hardened, render diagnostics in dev, snapshot toggling reliable.
- **Phase 1 started** — OHM basemap plugin installed and timeframe filtering wired into viewer/editor paths.

## Query Performance & Data Model

### High Priority

- [x] **Fix GeoJson cast N+1 on list endpoints**
  Added `EntityBuilder::withGeoJson()` which selects `ST_AsGeoJSON(geom)::jsonb AS geom_geojson` and `territory_geom_geojson` inline. The `GeoJson` cast now checks for `{key}_geojson` pre-computed attributes before falling back to a DB round-trip. `ListEntitiesAction` applies `withGeoJson()` by default.

- [x] **Hide `embedding` column by default**
  Added `$hidden = ['embedding', 'embedding_version']` to the `Entity` model.

- [x] **Fix temporal string sorting for BCE/CE ranges**
  Added normalized year columns for ordering/filtering and updated query/build paths to use integer temporal fields. Current canonical temporal storage is in `entity_temporal_ranges`; legacy entity-level temporal columns were removed during the canonical model cutover.

### Medium Priority

- [ ] **Add recursive ancestor/descendant queries (adjacency list)**
  The `parent()` / `children()` Eloquent relations require manual chaining for multi-level trees and have no recursive eager-load. Install [`staudenmeir/laravel-adjacency-list`](https://github.com/staudenmeir/laravel-adjacency-list) to get `ancestors()`, `descendants()`, `breadthFirst()` via PostgreSQL `WITH RECURSIVE` CTEs. Required for empire → kingdom → city-state hierarchies.

- [ ] **Document eager-load spec for relationship endpoints**
  `outgoingRelationships` + `incomingRelationships` each trigger N×2 additional queries when `sourceEntity`/`targetEntity` are accessed. Define a standard eager-load pattern for the entity detail endpoint:
  ```php
  Entity::with([
      'outgoingRelationships.targetEntity:entity_id,name,entity_type,entity_group',
      'incomingRelationships.sourceEntity:entity_id,name,entity_type,entity_group',
  ])->find($id);
  ```

- [ ] **Add composite indexes on `relationships` table for directional queries**
  Currently, "all relationships for entity X" requires two separate queries (one per direction). Add composite indexes to support filtered lookups by both direction and type:
  ```sql
  CREATE INDEX relationships_source_type_idx ON relationships (source_entity_id, relationship_type);
  CREATE INDEX relationships_target_type_idx ON relationships (target_entity_id, relationship_type);
  ```
  Also add an `allRelationshipsFor(string $entityId)` method to a `RelationshipBuilder` so controllers don't need to manually union both directions.

- [ ] **Decide on inverse relationship storage strategy**
  The model allows storing both `A [rules] B` and `B [governed_by] A`, but this is optional and inconsistently enforced. Decide: (a) always store both directions (requires a consistency mechanism on write), or (b) store one direction only and derive the inverse at query time. Option (b) is simpler but requires the `allRelationshipsFor` query above plus a `direction` field on API responses.

### Low Priority

- [ ] **Add per-type expression indexes on `attributes` JSONB**
  `hasAttribute('government_type', 'monarchy')` does a full GIN scan. For high-cardinality keys used in filters, add PostgreSQL expression indexes scoped to each entity type. 11 indexes planned — see `plans/attributes_and_geometry_snapshots.md` Section 5.

- [ ] **Harden `geometry_periods` lifecycle for time-varying geometries**
  Ensure all pipelines consistently write canonical period geometries (empires, routes, epidemics), validate non-overlapping periods per geometry role, and keep provenance fields complete.

---

## Data Pipeline

### High Priority

- [x] **Scaffold Python pipeline (`pipeline/`)**
  Created scraper, mapper, dedup, and embeddings modules. CLI entry point via `python -m pipeline scrape`. See `docs/implementation-docs/data_pipeline_architecture.md` for full documentation.

- [x] **Create Laravel import command and jobs**
  `pipeline:import` command reads JSONL files, dispatches `ImportEntityJob` per entity, and `ResolveRelationshipsJob` after batch completes. Relationship hints staged in `pipeline_relationship_hints` table.

- [x] **Create Laravel embedding command and jobs**
  `pipeline:embeddings` command dispatches `GenerateEntityEmbeddingJob` per entity. Calls OpenAI text-embedding-3-small, stores result in `embedding` column.

- [x] **Create `pipeline_relationship_hints` staging table migration**
  Migration `2026_03_21_100000_create_pipeline_relationship_hints_table.php` creates the staging table for relationship hints extracted from Wikidata during import.

- [x] **Add OpenAI config to `services.php`**
  Added `services.openai.api_key` and `services.openai.embedding_model` entries.

- [x] **Write v1 pipeline architecture docs**
  Created `docs/implementation-docs/data_pipeline_architecture.md` covering: system design, Python pipeline, JSONL schema, Laravel import layer, dedup strategy, relationship resolution, embedding generation, verification workflow, operational runbook, and v2+ roadmap.

### Medium Priority

- [ ] **Add composite unique index on `relationships` table**
  Prevent duplicate relationships by adding `UNIQUE(source_entity_id, target_entity_id, relationship_type)`. The `ResolveRelationshipsJob` does a soft check, but a DB-level constraint is safer.

- [ ] **Add `pg_trgm` GIN index on `entities.name`**
  Enables fast fuzzy DB dedup via `similarity()`. Expression index:
  ```sql
  CREATE INDEX entities_name_trgm_idx ON entities USING gin (name gin_trgm_ops);
  ```

- [ ] **Run initial v1 scrape and validate output**
  Execute the full pipeline run (all 5 groups, 100–200 entities per type), review JSONL output, import into dev DB, and verify entity/relationship counts.

- [ ] **Add `.gitignore` entries for pipeline artifacts**
  Add `pipeline/output/*.jsonl`, `pipeline/.env`, `pipeline/.venv/` to root or pipeline-level `.gitignore`.

### Low Priority

- [ ] **LLM enrichment pass (v2)**
  Use GPT-4o / Claude to generate `significance` text, resolve fuzzy dates, and fill missing attributes on `pipeline_draft` entities.

- [ ] **Auto-validation rules (v2)**
  Automated checks that promote `pipeline_draft` → `auto_validated`. Rules: has name, has type, has temporal data, coords in range, summary length > 50, QID well-formed.

- [ ] **Review queue UI (v2)**
  Admin panel page listing `needs_review` entities with inline editing and approve/reject actions.
