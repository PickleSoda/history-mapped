# Entity Model V2 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the current snapshot-centric entity model to a strict normalized write model with geometry periods and a derived timeline read model, without breaking existing admin/API workflows during rollout.

**Architecture:** Introduce new canonical tables alongside the current schema and switch API/read consumers incrementally to the new model. `geometry_snapshots` has already been hard-removed, so no snapshot backfill or compatibility adapter layer is required in this rollout.

**Tech Stack:** Laravel 13, PHP 8.4, PostgreSQL 16, PostGIS, Inertia/React route bindings, PHPUnit/Pest-style feature tests, GitNexus impact analysis.

---

## Impact Summary

GitNexus impact analysis for `GeometrySnapshot` returned `MEDIUM` risk with 12 direct importers. Directly affected files include:
- `api/app/Actions/GeometrySnapshot/*`
- `api/app/Actions/Relationship/CreateAutoSnapshotAction.php`
- `api/app/Actions/EntityGeoRef/PruneOrphanSnapshotGeoRefAction.php`
- `api/app/Http/Controllers/Admin/GeometrySnapshotController.php`
- `api/app/Http/Api/V1/Controllers/GeometrySnapshotController.php`
- `api/app/Http/Api/V1/Resources/GeometrySnapshotResource.php`
- `api/database/factories/GeometrySnapshotFactory.php`
- geometry snapshot feature/unit tests

Edge cases to resolve during migration:
- relationship-driven presence creation must become derived or geometry-period creation, not free snapshot creation
- map entity rendering currently reads snapshot territory geometry
- entity detail and count endpoints refer to `geometrySnapshots`
- snapshot geo-ref orphan pruning assumes snapshot ownership semantics
- generated JS route/action bindings for `geometry-snapshots` will become stale if endpoints move

---

## Execution Update (2026-04-06)

- [x] GeometrySnapshot hard-delete completed (no soft migration path)
- [x] Removed model, builders, actions, controllers, requests, resources, routes, factory, and snapshot-specific tests
- [x] Removed residual references in `EntityFactory`, `entity_geo_refs` migration, and `EntityGeoRefIntegrityTest`
- [x] Test suite status after cleanup: 144 passed
- [x] Task 1 core schema complete for aliases/tags/temporal ranges/locations (citations/link tables still pending)
- [x] Task 2 model graph complete and verified (`EntityModelV2RelationsTest` passing)
- [x] Task 3 backfill command + actions added and verified in Docker

## Timeline UX Gap Update (2026-04-07)

Validated strengths:
- `entity_timeline_entries` is the correct read model for timeline rendering and map playback.
- `geometry_periods` constraints correctly separate derived presence vs manual/event-driven territory periods.
- integer year fields in new V2 tables resolve BCE sorting issues.

Gap status:
1. `entity_timeline_entries` relationship/related-entity display fields implemented.
2. `relationships` integer year columns implemented with backfill/indexing.
3. geometry-period mutation path now triggers targeted timeline rebuild jobs.

---

### Task 5A: Add Timeline Display Denorm Columns

**Files:**
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_add_relationship_fields_to_entity_timeline_entries.php`
- Modify: `api/app/Builders/EntityTimelineEntryBuilder.php`
- Modify: `api/app/Actions/Timeline/ProjectEntityTimelineAction.php`
- Modify: `api/app/Http/Api/V1/Resources/EntityTimelineEntryResource.php`
- Test: `api/tests/Feature/Api/EntityTimelineApiTest.php`

- [x] add columns `relationship_type`, `related_entity_id`, `related_entity_name` to `entity_timeline_entries`
- [x] populate these fields during projection rebuild
- [x] expose these fields in timeline API resource for row badges + related-entity labels

### Task 5B: Add Integer Year Columns to Relationships

**Files:**
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_add_year_columns_to_relationships.php`
- Modify: relationship queries/builders that filter by time
- Test: `api/tests/Feature/Admin/RelationshipControllerTest.php`

- [x] add `start_year` and `end_year` integer columns
- [x] backfill from `temporal_start` / `temporal_end` text values
- [x] add composite index for range queries
- [x] use integer columns in projection and filtering paths

### Task 5C: Wire Rebuild on Geometry Period Mutation

**Files:**
- Modify: geometry-period create/update/delete action/controller paths
- Create (if needed): targeted timeline rebuild job/action
- Test: `api/tests/Feature/Feature/RebuildEntityTimelineCommandTest.php`

- [x] trigger targeted timeline rebuild when geometry periods change
- [x] ensure stale geometry cannot persist silently after period edits
- [x] verify `derived_at` semantics remain reliable for freshness checks

Validation run (Dockerized app + PostgreSQL):
- [x] `php artisan test tests/Feature/Api/EntityTimelineApiTest.php`
- [x] `php artisan test tests/Feature/Feature/RebuildEntityTimelineCommandTest.php`
- [x] `php artisan test tests/Feature/Admin/RelationshipControllerTest.php`

---

### Task 1: Add New Canonical Tables

**Files:**
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_entity_aliases_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_entity_tags_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_entity_temporal_ranges_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_entity_locations_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_geometry_periods_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_entity_timeline_entries_table.php`
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_create_citations_and_link_tables.php`
- Test: `api/tests/Feature/Feature/EntityModelV2SchemaTest.php`

- [ ] **Step 1: Write failing schema tests for the new tables and constraints**

Example assertions:
```php
expect(Schema::hasTable('geometry_periods'))->toBeTrue();
expect(Schema::hasColumns('geometry_periods', [
    'geometry_period_id', 'entity_id', 'period_type', 'start_year', 'end_year',
    'geom', 'territory_geom', 'provenance_mode', 'relationship_id', 'source_event_id'
]))->toBeTrue();
```

- [ ] **Step 2: Run the focused schema test to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2SchemaTest.php`
Expected: FAIL because the tables do not exist yet.

- [ ] **Step 3: Create migrations with hard DB constraints**

Required constraints:
- `geometry_periods.start_year <= end_year`
- `geometry_periods.geom IS NOT NULL OR geometry_periods.territory_geom IS NOT NULL`
- `geometry_periods.provenance_mode IN ('derived','manual')`
- derived rows require `relationship_id` or `source_event_id`
- `period_type='presence'` requires `relationship_id`

- [ ] **Step 4: Run migrations and rerun schema test**

Run: `docker compose exec app php artisan migrate`
Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2SchemaTest.php`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add api/database/migrations api/tests/Feature/Feature/EntityModelV2SchemaTest.php
git commit -m "feat: add entity model v2 schema tables"
```

### Task 2: Introduce New Eloquent Models and Entity Relations

**Files:**
- Create: `api/app/Models/EntityAlias.php`
- Create: `api/app/Models/EntityTag.php`
- Create: `api/app/Models/EntityTemporalRange.php`
- Create: `api/app/Models/EntityLocation.php`
- Create: `api/app/Models/GeometryPeriod.php`
- Create: `api/app/Models/EntityTimelineEntry.php`
- Modify: `api/app/Models/Entity.php`
- Test: `api/tests/Feature/Feature/EntityModelV2RelationsTest.php`

- [x] **Step 1: Write failing relation tests for the new model graph**

Test expectations:
- `Entity` has many aliases, tags, temporal ranges, locations, geometry periods, timeline entries
- `GeometryPeriod` belongs to entity and optionally relationship/source event

- [x] **Step 2: Run the relation test to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2RelationsTest.php`
Expected: FAIL with missing classes/relations.

- [x] **Step 3: Implement the new models and add relations to `Entity`**

Notes:
- keep existing `geometrySnapshots()` relation temporarily for compatibility
- add explicit `geometryPeriods()` and `timelineEntries()`
- do not remove existing relations in this task

- [x] **Step 4: Rerun relation tests**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2RelationsTest.php`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add api/app/Models api/tests/Feature/Feature/EntityModelV2RelationsTest.php
git commit -m "feat: add entity model v2 eloquent models"
```

### Task 3: Build Backfill Commands for Existing Entity Data

**Files:**
- Create: `api/app/Console/Commands/BackfillEntityModelV2Command.php`
- Create: `api/app/Actions/EntityModelV2/BackfillAliasesAction.php`
- Create: `api/app/Actions/EntityModelV2/BackfillTagsAction.php`
- Create: `api/app/Actions/EntityModelV2/BackfillTemporalRangesAction.php`
- Create: `api/app/Actions/EntityModelV2/BackfillLocationsAction.php`
- Create: `api/app/Actions/EntityModelV2/BackfillGeometryPeriodsAction.php`
- Test: `api/tests/Feature/Feature/BackfillEntityModelV2CommandTest.php`

- [x] **Step 1: Write a failing command test for backfill behavior**

Required coverage:
- `alternative_names` becomes alias rows
- `tags` becomes tag rows
- entity temporal/location fields become primary range/location rows
- `geometry_snapshots` become `geometry_periods` with provenance mapping (N/A in this rollout because snapshots were hard-removed)

- [x] **Step 2: Run the command test to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/BackfillEntityModelV2CommandTest.php`
Expected: FAIL because the command does not exist.

- [x] **Step 3: Implement the backfill command and actions**

Edge-case rules:
- if a snapshot has `relationship_id`, convert to `period_type='presence'`, `provenance_mode='derived'`
- if a snapshot has `source_event_id`, convert to `period_type='territory'`, `provenance_mode='derived'`
- if neither exists, convert to `provenance_mode='manual'` and record review flag for manual audit
- if entity has `geom` or `territory_geom`, write a primary `entity_locations` row rather than a period row

- [x] **Step 4: Run backfill test and a dry-run command**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/BackfillEntityModelV2CommandTest.php`
Run: `docker compose exec app php artisan entity-model-v2:backfill --dry-run`
Expected: PASS and a dry-run summary with counts by migrated table.

- [x] **Step 5: Commit**

```bash
git add api/app/Console/Commands api/app/Actions/EntityModelV2 api/tests/Feature/Feature/BackfillEntityModelV2CommandTest.php
git commit -m "feat: add entity model v2 backfill pipeline"
```

### Task 4: Replace Auto-Snapshot Creation with Geometry-Period Semantics

**Files:**
- Modify: `api/app/Actions/Relationship/CreateAutoSnapshotAction.php`
- Create: `api/app/Actions/Relationship/CreateDerivedPresencePeriodAction.php`
- Modify: `api/app/Actions/GeometrySnapshot/CreateLinkedSnapshotsAction.php`
- Modify: `api/app/Actions/Relationship/CreateRelationshipAction.php`
- Test: `api/tests/Feature/Admin/RelationshipControllerTest.php`

- [x] **Step 1: Add or update failing tests around relationship-derived presence creation**

New expectation:
- creating `fought_at`, `signed_by`, `born_in`, `died_in`, `resided_in` creates a derived geometry period or queues timeline projection input
- no free-standing manual snapshot row is created anymore

- [x] **Step 2: Run the focused relationship tests to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Admin/RelationshipControllerTest.php --filter=auto_snapshot`
Expected: FAIL against old snapshot behavior.

- [x] **Step 3: Implement compatibility transition**

Preferred path:
- keep `CreateAutoSnapshotAction` as a shim for one release
- internally delegate to `CreateDerivedPresencePeriodAction`
- mark old naming as deprecated in docblocks

- [x] **Step 4: Rerun relationship tests**

Run: `docker compose exec app php artisan test api/tests/Feature/Admin/RelationshipControllerTest.php`
Expected: PASS with geometry-period assertions.

- [x] **Step 5: Commit**

```bash
git add api/app/Actions/Relationship api/app/Actions/GeometrySnapshot/CreateLinkedSnapshotsAction.php api/tests/Feature/Admin/RelationshipControllerTest.php
git commit -m "refactor: derive presence periods from relationships"
```

### Task 5: Add Timeline Projection Pipeline

**Files:**
- Create: `api/app/Actions/Timeline/ProjectEntityTimelineAction.php`
- Create: `api/app/Console/Commands/RebuildEntityTimelineCommand.php`
- Create: `api/app/Builders/EntityTimelineEntryBuilder.php`
- Create: `api/app/Http/Api/V1/Resources/EntityTimelineEntryResource.php`
- Test: `api/tests/Feature/Api/EntityTimelineApiTest.php`
- Test: `api/tests/Feature/Feature/RebuildEntityTimelineCommandTest.php`

- [x] **Step 1: Write failing tests for timeline projection and API shape**

Required coverage:
- timeline entries derive from relationships and geometry periods
- entries include source table/id metadata
- no direct writes via admin UI

- [x] **Step 2: Run the focused tests to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/EntityTimelineApiTest.php api/tests/Feature/Feature/RebuildEntityTimelineCommandTest.php`
Expected: FAIL because the projection path does not exist.

- [x] **Step 3: Implement the projection builder and rebuild command**

Projection inputs:
- relationship-derived presence periods
- manual/derived territory periods
- primary temporal range fallback

- [x] **Step 4: Rerun timeline tests**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/EntityTimelineApiTest.php api/tests/Feature/Feature/RebuildEntityTimelineCommandTest.php`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add api/app/Actions/Timeline api/app/Console/Commands/RebuildEntityTimelineCommand.php api/app/Builders/EntityTimelineEntryBuilder.php api/app/Http/Api/V1/Resources/EntityTimelineEntryResource.php api/tests/Feature/Api/EntityTimelineApiTest.php api/tests/Feature/Feature/RebuildEntityTimelineCommandTest.php
git commit -m "feat: add derived entity timeline projection"
```

### Task 6: Migrate Admin and API Read Paths Off GeometrySnapshot

**Files:**
- Modify: `api/app/Http/Controllers/Admin/GeometrySnapshotController.php`
- Modify: `api/app/Http/Api/V1/Controllers/GeometrySnapshotController.php`
- Modify: `api/app/Http/Api/V1/Resources/GeometrySnapshotResource.php`
- Modify: `api/app/Http/Api/V1/Resources/GeometrySnapshotMapResource.php`
- Modify: `api/resources/js/routes/api/v1/entities/geometry-snapshots/index.ts`
- Modify: `api/resources/js/actions/App/Http/Api/V1/Controllers/GeometrySnapshotController.ts`
- Create: `api/app/Http/Api/V1/Controllers/EntityTimelineController.php`
- Test: `api/tests/Feature/Api/GeometrySnapshotApiTest.php`
- Test: `api/tests/Feature/Admin/GeometrySnapshotControllerTest.php`

- [x] **Step 1: Decide compatibility mode and write failing endpoint tests**

Compatibility recommendation:
- retain existing `geometry-snapshots` endpoints temporarily
- serve them from `geometry_periods` or timeline projection under an adapter
- add new timeline endpoint in parallel

- [x] **Step 2: Run existing snapshot endpoint tests to capture baseline**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/GeometrySnapshotApiTest.php api/tests/Feature/Admin/GeometrySnapshotControllerTest.php`
Expected: current baseline result captured before edits.

- [x] **Step 3: Implement adapter layer and timeline endpoint**

Rules:
- old snapshot resources become compatibility serializers over geometry periods
- admin create/update paths must reject forbidden manual presence entries
- JS route bindings must remain valid or be regenerated in the same task

- [x] **Step 4: Rerun endpoint tests**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/GeometrySnapshotApiTest.php api/tests/Feature/Admin/GeometrySnapshotControllerTest.php`
Expected: PASS with compatibility behavior preserved.

- [x] **Step 5: Commit**

```bash
git add api/app/Http/Controllers/Admin/GeometrySnapshotController.php api/app/Http/Api/V1/Controllers api/app/Http/Api/V1/Resources api/resources/js/routes/api/v1/entities/geometry-snapshots/index.ts api/resources/js/actions/App/Http/Api/V1/Controllers/GeometrySnapshotController.ts api/tests/Feature/Api/GeometrySnapshotApiTest.php api/tests/Feature/Admin/GeometrySnapshotControllerTest.php
git commit -m "feat: migrate snapshot endpoints to geometry period adapters"
```

### Task 7: Update Map, Entity Detail, and Geo-Ref Cleanup Behavior

**Files:**
- Modify: `api/app/Models/Entity.php`
- Modify: `api/app/Actions/EntityGeoRef/PruneOrphanSnapshotGeoRefAction.php`
- Create: `api/app/Actions/EntityGeoRef/PruneOrphanGeometryPeriodGeoRefAction.php`
- Test: `api/tests/Feature/Api/MapEntitiesThresholdTest.php`
- Test: `api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php`
- Test: `api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`

- [x] **Step 1: Write or update failing tests for read-model consumers**

Coverage:
- map threshold endpoint reads matching geometry periods for territories
- entity detail counts migrate from `geometrySnapshots` to geometry periods/timeline counts
- geo-ref cleanup does not delete shared entity-level references incorrectly

- [x] **Step 2: Run focused tests to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/MapEntitiesThresholdTest.php api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`
Expected: FAIL once model lookups are changed.

- [x] **Step 3: Implement the read path switch and geo-ref pruning adjustments**

Edge case:
- period-level georef cleanup must distinguish entity-primary refs from derived/manual period refs

- [x] **Step 4: Rerun the focused tests**

Run: `docker compose exec app php artisan test api/tests/Feature/Api/MapEntitiesThresholdTest.php api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/Models/Entity.php api/app/Actions/EntityGeoRef api/tests/Feature/Api/MapEntitiesThresholdTest.php api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php
git commit -m "refactor: move map and detail reads to geometry periods"
```

### Task 8: Deprecate Old Columns and Remove Dual-Write Paths

**Files:**
- Create: `api/database/migrations/xxxx_xx_xx_xxxxxx_deprecate_snapshot_and_entity_columns.php`
- Modify: `api/database/migrations/2026_03_18_000002_create_entities_table.php` (documentation comments only if desired)
- Modify: `docs/entity-model/attributes.md`
- Modify: `docs/entity-model/for-historians.md`
- Modify: `docs/entity-model/for-geodata-contributors.md`
- Test: `api/tests/Feature/Feature/EntityModelV2DeprecationTest.php`

- [x] **Step 1: Write failing tests or assertions for deprecated access paths**

Required behavior:
- no new writes to legacy entity temporal/location columns except temporary compatibility sync if still enabled
- no new writes to `geometry_snapshots` after cutover flag is enabled

- [x] **Step 2: Run deprecation tests to verify failure**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2DeprecationTest.php`
Expected: FAIL before cutover logic exists.

- [x] **Step 3: Add feature flag or staged cutover guard and update docs**

Recommended flag names:
- `entity_model_v2_write_enabled`
- `geometry_snapshot_compat_read_enabled`

- [x] **Step 4: Rerun tests and spot-check docs**

Run: `docker compose exec app php artisan test api/tests/Feature/Feature/EntityModelV2DeprecationTest.php`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/database/migrations docs/entity-model api/tests/Feature/Feature/EntityModelV2DeprecationTest.php
git commit -m "chore: deprecate legacy snapshot and entity write paths"
```

### Task 9: Full Verification and Change-Scope Review

**Files:**
- Test: `api/tests/Unit/GeometrySnapshotBuilderTest.php`
- Test: `api/tests/Feature/Admin/RelationshipControllerTest.php`
- Test: `api/tests/Feature/Admin/GeometrySnapshotControllerTest.php`
- Test: `api/tests/Feature/Api/GeometrySnapshotApiTest.php`
- Test: `api/tests/Feature/Api/MapEntitiesThresholdTest.php`
- Test: `api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php`
- Test: `api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`

- [ ] **Step 1: Run the impacted test suite from the GitNexus blast radius**

Run: `docker compose exec app php artisan test api/tests/Unit/GeometrySnapshotBuilderTest.php api/tests/Feature/Admin/RelationshipControllerTest.php api/tests/Feature/Admin/GeometrySnapshotControllerTest.php api/tests/Feature/Api/GeometrySnapshotApiTest.php api/tests/Feature/Api/MapEntitiesThresholdTest.php api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`
Expected: PASS.

- [ ] **Step 2: Run a broader Laravel test pass if time permits**

Run: `docker compose exec app php artisan test`
Expected: PASS or unrelated failures documented.

- [ ] **Step 3: Run GitNexus change-scope validation before merge or commit batching**

Run: `npx gitnexus@latest detect_changes all`
Expected: only expected schema/model/controller/resource/test areas changed.

- [ ] **Step 4: Produce rollout notes**

Document:
- required backfill order
- safe rollback point
- compatibility flags used
- data audit queries for manual geometry periods

- [ ] **Step 5: Commit final verification artifacts**

```bash
git add .
git commit -m "test: verify entity model v2 migration rollout"
```
