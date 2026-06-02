# OHM Point-Only Border Import First Pass Implementation Plan

> **Status (as of 2026-06-01):** COMPLETED. Representative-point derivation, point-only mapper output, Laravel importer `geom`-only persistence, and timeline/geometry-period summary/detail contracts are all implemented and tested.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop persisting OHM border polygons in the built JSONL and Laravel border import path while preserving OHM relation georefs, time-aware geometry periods, and representative map markers.

**Architecture:** Keep full OHM relation geometry transient inside the Python pipeline only long enough to derive one representative point per imported stage, then emit point-only `_geometry_periods[*].geojson` records into the final OHM JSONL. Preserve `entity_geo_refs` and `geometry_periods`, but make OHM-imported `geometry_periods` write to `geom` only, leaving `territory_geom` empty for this import path. Do not change schema, frontend basemap integration, or the generic manual geometry authoring model in this first pass.

**Tech Stack:** Python 3.10, existing OHM staged pipeline, Shapely-backed geometry assembly with fallback centroid helpers, Laravel queue/import jobs, PostGIS `geom` and `territory_geom` columns, pytest, Laravel feature tests via Docker Compose.

---

## File Structure And Responsibilities

- Modify: `pipeline/ohm_borders/fetcher.py`
  - Add a focused helper that derives one representative point from transient OHM polygon geometry.
  - Reuse the existing Shapely path when available, with a deterministic fallback for environments where Shapely is unavailable at runtime.

- Modify: `pipeline/ohm_borders/mapper.py`
  - Keep temporal and relation metadata unchanged.
  - Replace polygon-shaped stage payloads in `_geometry_periods[*].geojson` with point-only GeoJSON derived from the transient OHM geometry.
  - Do not introduce a broader contract reshape in this first pass.

- Modify: `pipeline/tests/test_ohm_borders_fetcher.py`
  - Lock the representative-point derivation rules at the geometry-helper level.

- Modify: `pipeline/tests/test_ohm_borders_mapper.py`
  - Lock the new point-only mapper contract and ensure reversed-year stages are still skipped.

- Modify: `pipeline/tests/test_ohm_borders_stages.py`
  - Lock the staged build output so the final JSONL no longer carries imported OHM polygons.

- Modify: `api/app/Jobs/ImportBorderEntityJob.php`
  - Preserve georef creation and time-range syncing.
  - Persist OHM-imported geometry periods to `geom` only, not `territory_geom`.
  - Keep the existing representative-point hydration into the primary entity location, now driven by point payloads instead of polygons.

- Modify: `api/app/Http/Api/V1/Controllers/EntityTimelineController.php`
  - Keep `index` as a summary-only endpoint and `show` as the full-geometry detail endpoint.
  - Ensure point-only timeline rows can surface cheap summary `geom` data while `territory_geom` stays detail-only.

- Modify: `api/app/Http/Api/V1/Resources/EntityTimelineEntrySummaryResource.php`
  - Serialize summary-safe timeline fields only.
  - Normalize the SQL-side summary point alias into the public `geom` field so point-only rows do not require a detail fetch.

- Modify: `api/tests/Feature/Api/EntityTimelineApiTest.php`
  - Lock the point-first summary/detail timeline contract for imported OHM rows and manually curated polygon rows.

- Modify: `api/resources/js/components/entity-history-panel.tsx`
  - Reuse summary-point geometry directly.
  - Lazy-load detail only when a selected entry still needs full territory geometry.

- Modify: `api/resources/js/components/__tests__/entity-history-panel.test.tsx`
  - Lock no-extra-fetch behavior for point-only timeline summaries and detail fetch behavior for territory cases.

- Modify: `api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php`
  - Preserve the list/detail split for geometry periods so summary rows stay light and edit views still receive full geometry.

- Modify: `api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`
  - Lock summary omission of heavy geometry and detail availability for edit/manual polygon flows.

- Modify: `api/resources/js/components/entity-geometry-periods-panel.tsx`
  - Keep the list bound to summary rows and fetch detail on edit or focused selection.

- Modify: `api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`
  - Lock lazy detail loading before edit so point-only imported periods do not bloat list payloads.

- Verify only: `api/routes/api.php`
  - Keep both timeline routes public and separate: index for summary, show for detail.

- Modify: `api/tests/Feature/Feature/ImportBordersCommandTest.php`
  - Lock the Laravel import contract so OHM-imported periods become point rows and reverse-lookup georefs still attach correctly.

- Modify: `docs/schemas/pipeline-entity-record.md`
  - Document that the OHM borders build output uses point-only `_geometry_periods[*].geojson` in this path.

- Modify: `pipeline/ohm_borders/README.md`
  - Document the new storage policy: transient OHM polygons in the pipeline, point-only importer output, unchanged georef attachment.

Commit note:

- Exclude: `api/app/Providers/AppServiceProvider.php`
  - Commit `1bc298c` also added a local Vite fallback there, but that infrastructure change is unrelated to OHM geometry handling and is not part of this plan extension.

## Explicit Non-Goals For This First Pass

- No database migration.
- No enum expansion for a new location method.
- No change to `entity_geo_refs` semantics.
- No redesign of manual/admin geometry editing flows; only preservation of the existing summary/detail contract is covered below.
- No frontend rewrite to highlight OHM features directly from georefs.
- No removal of `geometry_periods` as a concept.

These are valid follow-up tasks, but they are intentionally excluded from the minimal first pass.

---

### Task 1: Lock Representative-Point And Point-Only Mapper Contracts With Failing Python Tests

**Files:**
- Modify: `pipeline/tests/test_ohm_borders_fetcher.py`
- Modify: `pipeline/tests/test_ohm_borders_mapper.py`
- Modify: `pipeline/tests/test_ohm_borders_stages.py`

- [x] **Step 1: Add a focused representative-point helper test in `pipeline/tests/test_ohm_borders_fetcher.py`**

Add a test that feeds a simple polygon or multipolygon GeoJSON into the new helper and expects a point result:

```python
point = derive_representative_point({
    "type": "MultiPolygon",
    "coordinates": [[[[0, 0], [4, 0], [4, 4], [0, 0]]]],
})

assert point == {"type": "Point", "coordinates": [expected_x, expected_y]}
```

The assertion should validate point shape and deterministic coordinates, not a polygon echo.

- [x] **Step 2: Update mapper tests to expect point-only `_geometry_periods[*].geojson`**

In `pipeline/tests/test_ohm_borders_mapper.py`, change the existing stage assertions from polygon output to point output. Keep the temporal, label, and `ohm_relation_id` expectations intact.

Make the failing-test checkpoint explicit. The updated assertion should look more like:

```python
assert period["geojson"]["type"] == "Point"
assert len(period["geojson"]["coordinates"]) == 2
```

This should fail immediately against the current `MultiPolygon` output and makes the contract change unambiguous.

- [x] **Step 3: Update staged build tests to expect point-only final JSONL**

In `pipeline/tests/test_ohm_borders_stages.py`, update the build-stage expectations so the merged `built/` and `final/` JSONL artifacts show point payloads inside `_geometry_periods` instead of polygons.

The staged pipeline should still preserve:

- `_ohm_relation_id`
- stage ordering
- temporal bounds
- labels
- `external_tags`

- [x] **Step 4: Run the focused Python tests to verify they fail**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
```

Expected:

- mapper and stage assertions fail because the current code still emits `MultiPolygon`
- the new helper test fails because the representative-point helper does not exist yet

- [x] **Step 5: Commit the failing-test checkpoint**

```powershell
git add pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py
git commit -m "test: lock OHM point-only mapper contract"
```

### Task 2: Implement Representative-Point Derivation In The OHM Pipeline

**Files:**
- Modify: `pipeline/ohm_borders/fetcher.py`
- Modify: `pipeline/ohm_borders/mapper.py`

- [x] **Step 1: Add a representative-point helper to `pipeline/ohm_borders/fetcher.py`**

Implement a small helper, for example `derive_representative_point(geometry: dict[str, Any]) -> dict[str, Any] | None`, with this behavior:

- return the geometry unchanged when it is already a `Point`
- for `Polygon` and `MultiPolygon`, use Shapely `representative_point()` as the primary path so the point stays inside the geometry when possible
- if Shapely is unavailable for this helper path, fall back to a deterministic ring-based center using the existing ring helpers already in the file
- prefer the largest available outer ring for the fallback, then use its centroid helper rather than inventing a second polygon traversal strategy
- return `None` when the geometry is missing or unusable

Keep this helper local to the OHM pipeline. Do not broaden it into a generic geospatial abstraction yet.

- [x] **Step 2: Update `pipeline/ohm_borders/mapper.py` to emit point-only stage payloads**

Replace this stage payload shape:

```python
"geojson": stage.get("geometry")
```

with logic equivalent to:

```python
"geojson": derive_representative_point(stage.get("geometry"))
```

Preserve the current keys and ordering:

- `ohm_relation_id`
- `external_type`
- `start_year`
- `end_year`
- `start_date`
- `end_date`
- `geojson`
- `label`
- `external_tags`

Do not add new top-level `territory_geojson` output in this first pass. The minimal contract change is to keep `_geometry_periods[*].geojson` but make it point-only.

- [x] **Step 3: Keep transient polygon geometry out of the final JSONL only**

Do not change `parse` artifacts or upstream raw geometry assembly in this pass. The parsed OHM records may still carry stage polygons internally; only the built and final importer-facing JSONL should stop carrying them.

- [x] **Step 4: Run the focused Python tests to verify they pass**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
```

Expected: PASS.

- [x] **Step 5: Commit the pipeline implementation checkpoint**

```powershell
git add pipeline/ohm_borders/fetcher.py pipeline/ohm_borders/mapper.py pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py
git commit -m "feat: emit point-only OHM border stage geometry"
```

### Task 3: Lock The Laravel Border Import Contract With Failing Tests

**Files:**
- Modify: `api/tests/Feature/Feature/ImportBordersCommandTest.php`

- [x] **Step 1: Update fixture records to use point-only `_geometry_periods[*].geojson`**

Replace the existing `MultiPolygon` fixtures in `ImportBordersCommandTest` with point fixtures such as:

```php
'geojson' => [
    'type' => 'Point',
    'coordinates' => [12.5, 41.9],
],
```

Keep the same temporal ranges and relation ids so the importer behavior is compared on equal metadata.

- [x] **Step 2: Add assertions that imported OHM periods write to `geom`, not `territory_geom`**

For every imported OHM geometry period, assert:

- `geom` is populated
- `territory_geom` is null
- `period_type` remains `territory`

This keeps the semantics of a territorial time slice while storing only its marker geometry.

Make the assertions concrete in the test body, for example by loading a created `GeometryPeriod` row and checking:

```php
$period = GeometryPeriod::query()->where('entity_id', $entity->entity_id)->firstOrFail();

$this->assertNotNull($period->geom);
$this->assertNull($period->territory_geom);
$this->assertSame('territory', $period->period_type->value);
```

- [x] **Step 3: Add assertions that the primary entity location remains point-only**

Assert that the importer still hydrates the entity’s primary location from the first available OHM stage, but now as a point:

- `entity_locations.geom` is populated
- `entity_locations.territory_geom` remains null for this OHM import path

- [x] **Step 4: Run the focused Laravel test to verify it fails**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected:

- tests fail because the current import job still writes OHM stage payloads to `geometry_periods.territory_geom`

- [x] **Step 5: Commit the failing importer-test checkpoint**

```powershell
git add api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "test: lock point-only OHM import behavior"
```

### Task 4: Make The Border Importer Persist OHM Period Points Only

**Files:**
- Modify: `api/app/Jobs/ImportBorderEntityJob.php`

- [x] **Step 1: Change `upsertGeometryPeriods()` to write OHM-imported points into `geom`**

Update the `GeometryPeriod::query()->create([...])` payload so OHM-imported stages set:

```php
'geom' => $geojson,
'territory_geom' => null,
```

instead of the current `territory_geom => $geojson` behavior.

Do the same for any future update-or-reuse branch in this method if a new branch is introduced during implementation.

- [x] **Step 2: Add a hard guard against polygon regression in the OHM import path**

Before persisting the stage geometry, verify the payload is a point-like geometry for this path. If the payload is unexpectedly polygonal, either skip it with a targeted log entry or fail fast in the narrowest way the existing import conventions allow.

This keeps the importer honest even if a later mapper change accidentally reintroduces polygons.

- [x] **Step 3: Keep georef creation and representative-point hydration intact**

Do not change:

- `firstOrCreateGeoRef()`
- `attachGeometryPeriodGeoRefs()`
- `syncEntityTemporalBounds()`

Keep `hydrateEntityGeometry()` in place so the primary entity location still gets a base point from the imported OHM stages. Because the mapper now emits point-only stage payloads, the existing hydrator should naturally populate `entity_locations.geom`.

- [x] **Step 4: Run the focused Laravel test to verify it passes**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected: PASS.

- [x] **Step 5: Commit the importer implementation checkpoint**

```powershell
git add api/app/Jobs/ImportBorderEntityJob.php api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "feat: store OHM imported geometry periods as points"
```

### Task 5: Update Operator Docs And Verify The First-Pass Contract End To End

**Files:**
- Modify: `docs/schemas/pipeline-entity-record.md`
- Modify: `pipeline/ohm_borders/README.md`

- [x] **Step 1: Update the pipeline entity schema doc**

In `docs/schemas/pipeline-entity-record.md`, document that the OHM borders build output keeps `_geometry_periods[*].geojson` as the importer-facing spatial field, but that this first pass now emits a representative `Point` instead of a polygonal OHM border geometry.

Make the note explicit that full OHM polygons remain transient in the pipeline and are no longer persisted through this importer path.

Include the rationale, not just the shape change:

- final JSONL should stay lightweight
- OHM feature identity still lives in `entity_geo_refs`
- representative points still support map markers and reverse lookup
- `territory_geom` stays available for manual or curated local boundary authoring outside this import path

- [x] **Step 2: Update the OHM borders README**

In `pipeline/ohm_borders/README.md`, add a short section explaining:

- the pipeline still assembles full OHM geometry transiently
- built/final JSONL now carries point-only stage geometry for border imports
- Laravel import still creates `entity_geo_refs` and `geometry_periods`, but OHM-imported periods are point-only in this pass
- local persisted polygons are intentionally deferred to later curated or tile-driven flows

- [x] **Step 3: Run the focused Python and Laravel checks together**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected: both commands pass.

- [x] **Step 4: Run one smoke build plus sync import using an OHM fixture artifact**

Use an existing small fixture-backed run or temporary artifact directory and run:

```powershell
py -m pipeline borders build --run-id <fixture-run-id> --artifact-dir <fixture-artifact-dir> --force
docker compose -f docker/docker-compose.yml exec app php -d memory_limit=1024M artisan pipeline:import-borders <fixture-jsonl-path> --sync --force --batch-id=ohm-point-first-pass-smoke
```

Expected:

- built JSONL contains point-only `_geometry_periods[*].geojson`
- imported OHM periods have `geom` populated and `territory_geom` empty
- georef rows still exist for the root OHM relation and any stage relations

- [x] **Step 5: Commit the docs and verification checkpoint**

```powershell
git add docs/schemas/pipeline-entity-record.md pipeline/ohm_borders/README.md
git commit -m "docs: describe point-only OHM border import contract"
```

### Task 6: Preserve Point-First Timeline Summary And Detail Contracts

**Files:**
- Modify: `api/app/Http/Api/V1/Controllers/EntityTimelineController.php`
- Modify: `api/app/Http/Api/V1/Resources/EntityTimelineEntrySummaryResource.php`
- Modify: `api/tests/Feature/Api/EntityTimelineApiTest.php`
- Modify: `api/resources/js/components/entity-history-panel.tsx`
- Modify: `api/resources/js/components/__tests__/entity-history-panel.test.tsx`
- Verify only: `api/routes/api.php`

- [x] **Step 1: Extend the failing API and frontend tests around summary-vs-detail geometry**

In `api/tests/Feature/Api/EntityTimelineApiTest.php`, update or add assertions that distinguish the compact summary payload from the full detail payload:

- point-only timeline rows must return `has_geom: true`
- point-only timeline rows must return `has_territory_geom: false`
- the index payload must expose `geom.type === "Point"`
- the index payload must not expose `territory_geom`
- detail payloads must remain the place where manual polygon geometry is returned

In `api/resources/js/components/__tests__/entity-history-panel.test.tsx`, add or strengthen the two key UI expectations:

- clicking a point-only summary entry must not trigger `/timeline/{id}`
- clicking a territory-bearing entry must still trigger `/timeline/{id}` so the viewer can load full detail on demand

- [x] **Step 2: Run the focused timeline tests to verify they fail if the summary/detail contract drifts**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php
Push-Location api; pnpm vitest run resources/js/components/__tests__/entity-history-panel.test.tsx; Pop-Location
```

Expected:

- the current summary resource/query alias mismatch should fail fast in the API test because `EntityTimelineController` selects `geom_geojson` while `EntityTimelineEntrySummaryResource` currently reads the public `geom` field
- any regression that eagerly detail-fetches point-only rows fails in the Vitest suite

- [x] **Step 3: Align the timeline controller and summary resource with the point-first contract**

Keep `EntityTimelineController::index()` as the light list endpoint and `show()` as the heavy detail endpoint.

The summary endpoint should:

- keep `has_geom` and `has_territory_geom`
- expose summary point geometry only when it is cheap to inline
- avoid returning `territory_geom` on the index route

Match the aliasing pattern already used in `EntitySummaryResource`. If the controller selects a summary alias such as `geom_geojson`, the summary resource must normalize that alias back into the public `geom` field rather than relying on the full `geom` attribute to be loaded.

Treat this as a concrete first fix, not just a generic cleanup. The current seam to correct is:

```php
// controller summary query
->selectRaw("CASE WHEN geom IS NOT NULL AND ST_GeometryType(geom) = 'ST_Point' THEN ST_AsGeoJSON(geom)::jsonb ELSE NULL END as geom_geojson")

// summary resource public payload
'geom' => $this->geom_geojson,
```

Keep `territory_geom` detail-only.

- [x] **Step 4: Keep `entity-history-panel.tsx` lazy only when full geometry is actually needed**

Preserve this decision tree in the component:

- if the selected summary row already includes point `geom` and has no territory geometry, use it directly and skip the detail fetch
- if the selected row advertises `has_territory_geom`, fetch `timeline/{id}` and render the returned detail geometry
- if the selected row has neither geometry flag, do not fetch detail

Do not reintroduce hover-driven geometry fetches or broad overview deduping in this pass.

- [x] **Step 5: Run the focused timeline tests to verify they pass**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php
Push-Location api; pnpm vitest run resources/js/components/__tests__/entity-history-panel.test.tsx; Pop-Location
```

Expected: PASS.

- [x] **Step 6: Commit the timeline summary/detail checkpoint**

```powershell
git add api/app/Http/Api/V1/Controllers/EntityTimelineController.php api/app/Http/Api/V1/Resources/EntityTimelineEntrySummaryResource.php api/tests/Feature/Api/EntityTimelineApiTest.php api/resources/js/components/entity-history-panel.tsx api/resources/js/components/__tests__/entity-history-panel.test.tsx
git commit -m "feat: preserve point-first timeline geometry summaries"
```

### Task 7: Preserve Geometry-Period Summary And Detail Editing Contracts

**Files:**
- Modify: `api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php`
- Modify: `api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`
- Modify: `api/resources/js/components/entity-geometry-periods-panel.tsx`
- Modify: `api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`

- [x] **Step 1: Extend the failing admin/controller tests for summary-only lists and lazy detail loading**

In `api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php`, lock both sides of the contract:

- `index` returns `has_geom` and `has_territory_geom`
- `index` omits `geom` and `territory_geom`
- `show` returns the actual geometry payload needed for editing
- point-only rows continue to report `has_geom: true` and `has_territory_geom: false`
- manual polygon rows continue to round-trip through `show`, `store`, and `update`

In `api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx`, explicitly require the edit flow to fetch `detailUrlFn(id)` before populating the edit form.

- [x] **Step 2: Run the focused geometry-period tests to verify they fail if the list/detail split regresses**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityGeometryPeriodControllerTest.php
Push-Location api; pnpm vitest run resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx; Pop-Location
```

Expected:

- the Laravel test fails if list responses start inlining geometry again or if point flags drift
- the Vitest case fails if edit mode assumes geometry is already in the list response

- [x] **Step 3: Preserve the compact controller payload and lazy edit behavior**

Keep `EntityGeometryPeriodController::index()` summary-only and `show()` detail-full.

The controller and component should continue to support this split:

- list rows stay compact for imported OHM point periods and manual polygon periods alike
- edit mode fetches the selected period detail before hydrating the form
- point-only imported rows remain editable without requiring list payload geometry

Only widen the payload if a concrete regression forces it; otherwise keep the commit `1bc298c` pattern intact.

- [x] **Step 4: Run the focused geometry-period tests to verify they pass**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Admin/EntityGeometryPeriodControllerTest.php
Push-Location api; pnpm vitest run resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx; Pop-Location
```

Expected: PASS.

- [x] **Step 5: Commit the geometry-period summary/detail checkpoint**

```powershell
git add api/app/Http/Controllers/Admin/EntityGeometryPeriodController.php api/tests/Feature/Admin/EntityGeometryPeriodControllerTest.php api/resources/js/components/entity-geometry-periods-panel.tsx api/resources/js/components/__tests__/entity-geometry-periods-panel.test.tsx
git commit -m "feat: preserve lazy geometry period detail loading"
```

---

## Handoff Notes For The Next Pass

After this first pass lands, the next migration can decide whether to:

- add an explicit location method for OHM-derived representative points instead of reusing `ohm_nominatim`
- make map and timeline APIs return OHM feature references alongside local points where summary/detail contracts are not enough
- stop relying on local `geometry_periods` for OHM border overlays entirely and shift entity-specific polygon highlighting to direct OHM tile or feature-resolution flows
- add richer point provenance fields when historians need to distinguish representative-point, Wikidata-point, and capital-point strategies

Those are intentionally deferred so the first pass can remain a narrow, reversible contract change.