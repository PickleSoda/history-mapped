# Legacy Erasure Inventory (Task 10 Step 1)

> Historical status (completed): this inventory captured pre-hard-drop usage before Task 13 landed.
> Keep for audit traceability; current codebase should no longer contain active runtime usage of listed artifacts.

Date: 2026-04-07
Scope:
- Legacy table: geometry_snapshots compatibility surface
- Legacy entity columns planned for removal: geom, territory_geom, location_name, temporal_start, temporal_end, temporal_start_year, temporal_end_year, alternative_names, tags

## 1) Active compatibility surface for geometry-snapshots

Backend compatibility endpoints/controllers/resources:
- api/app/Http/Controllers/Admin/GeometrySnapshotController.php
- api/app/Http/Api/V1/Resources/GeometrySnapshotResource.php
- api/app/Http/Api/V1/Resources/GeometrySnapshotMapResource.php
- api/routes/web.php
- api/routes/api.php

Generated JS bindings still exposing compatibility routes/actions:
- api/resources/js/routes/entities/geometry-snapshots/index.ts
- api/resources/js/routes/api/v1/entities/geometry-snapshots/index.ts
- api/resources/js/actions/App/Http/Controllers/Admin/GeometrySnapshotController.ts
- api/resources/js/actions/App/Http/Api/V1/Controllers/GeometrySnapshotController.ts
- api/resources/js/routes/entities/index.ts
- api/resources/js/routes/api/v1/entities/index.ts

Tests still asserting compatibility behavior:
- api/tests/Feature/Admin/GeometrySnapshotControllerTest.php
- api/tests/Feature/Api/GeometrySnapshotApiTest.php

## 2) Legacy entity column read/write usage (backend)

Core model and builders:
- api/app/Models/Entity.php (fillable/casts include legacy columns)
- api/app/Builders/EntityBuilder.php (spatial + temporal queries against entities.geom/territory_geom/temporal_* and tags)

Create/update write paths:
- api/app/Actions/Entity/CreateEntityAction.php
- api/app/Actions/Entity/UpdateEntityAction.php

Validation contracts still accepting legacy payload fields:
- api/app/Http/Requests/Admin/StoreEntityRequest.php
- api/app/Http/Requests/Admin/UpdateEntityRequest.php
- api/app/Http/Api/V1/Requests/UpdateEntityRequest.php

API resources returning legacy columns:
- api/app/Http/Api/V1/Resources/EntityResource.php
- api/app/Http/Api/V1/Resources/EntitySummaryResource.php
- api/app/Http/Api/V1/Resources/EntityMapResource.php

Secondary consumers currently tied to legacy columns:
- api/app/Jobs/GenerateEntityEmbeddingJob.php
- api/app/Actions/Relationship/CreateDerivedPresencePeriodAction.php (sources geom from entities)
- api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php (falls back to entities geometry)

## 3) Legacy column usage (frontend/admin)

Entity create/edit forms and pages:
- api/resources/js/components/entity-form.tsx
- api/resources/js/pages/entities/create.tsx
- api/resources/js/pages/entities/edit.tsx
- api/resources/js/pages/entities/show.tsx
- api/resources/js/pages/entities/index.tsx
- api/resources/js/types/entity.ts

Relationship/history UI still expects temporal_start/temporal_end:
- api/resources/js/components/relationship-panel.tsx
- api/resources/js/components/entity-history-panel.tsx
- api/resources/js/components/__tests__/entity-history-panel.test.tsx

## 4) Seeders, factories, and backfill dependencies

Legacy-heavy seeding still writes legacy entity columns directly:
- api/database/seeders/EntitySeeder.php

Backfill actions depend on legacy columns as migration source (expected until hard drop):
- api/app/Actions/EntityModelV2/BackfillAliasesAction.php
- api/app/Actions/EntityModelV2/BackfillTagsAction.php
- api/app/Actions/EntityModelV2/BackfillTemporalRangesAction.php
- api/app/Actions/EntityModelV2/BackfillLocationsAction.php
- api/app/Console/Commands/BackfillEntityModelV2Command.php

## 5) Test files needing update/replacement during hard-drop

Deprecation + migration safety tests:
- api/tests/Feature/Feature/EntityModelV2DeprecationTest.php
- api/tests/Feature/Feature/BackfillEntityModelV2CommandTest.php
- api/tests/Feature/Feature/EntityModelV2SchemaTest.php

Read-path behavior tests impacted by field removal:
- api/tests/Feature/Api/MapEntitiesThresholdTest.php
- api/tests/Feature/Api/EntityTimelineApiTest.php
- api/tests/Feature/Api/EntityDetailGeometrySnapshotsCountTest.php
- api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php

## 6) Recommended removal order

1. Remove geometry-snapshot compatibility controllers/routes/resources and regenerate JS bindings.
2. Convert read paths and API resources to V2-only sources (entity_locations/entity_temporal_ranges/geometry_periods/entity_timeline_entries).
3. Convert forms/DTOs/requests to V2 payload shape; stop accepting legacy entity fields.
4. Migrate seeders/factories to V2-only setup.
5. Hard-drop legacy columns and any residual snapshot artifacts in final migration.

## 7) Exit criteria for hard-drop window

- No runtime references to entities legacy columns in app/, resources/js/, routes/, and jobs.
- No geometry-snapshots compatibility routes/actions/resources/controllers.
- Backfill command no longer required for normal app operation (one-time migration only).
- Full test suite green after schema drop migration.
