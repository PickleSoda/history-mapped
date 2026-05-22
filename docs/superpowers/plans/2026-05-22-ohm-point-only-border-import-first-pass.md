# OHM Point-Only Border Import First Pass Implementation Plan

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

- Modify: `api/tests/Feature/Feature/ImportBordersCommandTest.php`
  - Lock the Laravel import contract so OHM-imported periods become point rows and reverse-lookup georefs still attach correctly.

- Modify: `docs/schemas/pipeline-entity-record.md`
  - Document that the OHM borders build output uses point-only `_geometry_periods[*].geojson` in this path.

- Modify: `pipeline/ohm_borders/README.md`
  - Document the new storage policy: transient OHM polygons in the pipeline, point-only importer output, unchanged georef attachment.

## Explicit Non-Goals For This First Pass

- No database migration.
- No enum expansion for a new location method.
- No change to `entity_geo_refs` semantics.
- No change to manual/admin geometry editing flows.
- No frontend rewrite to highlight OHM features directly from georefs.
- No removal of `geometry_periods` as a concept.

These are valid follow-up tasks, but they are intentionally excluded from the minimal first pass.

---

### Task 1: Lock Representative-Point And Point-Only Mapper Contracts With Failing Python Tests

**Files:**
- Modify: `pipeline/tests/test_ohm_borders_fetcher.py`
- Modify: `pipeline/tests/test_ohm_borders_mapper.py`
- Modify: `pipeline/tests/test_ohm_borders_stages.py`

- [ ] **Step 1: Add a focused representative-point helper test in `pipeline/tests/test_ohm_borders_fetcher.py`**

Add a test that feeds a simple polygon or multipolygon GeoJSON into the new helper and expects a point result:

```python
point = derive_representative_point({
    "type": "MultiPolygon",
    "coordinates": [[[[0, 0], [4, 0], [4, 4], [0, 0]]]],
})

assert point == {"type": "Point", "coordinates": [expected_x, expected_y]}
```

The assertion should validate point shape and deterministic coordinates, not a polygon echo.

- [ ] **Step 2: Update mapper tests to expect point-only `_geometry_periods[*].geojson`**

In `pipeline/tests/test_ohm_borders_mapper.py`, change the existing stage assertions from polygon output to point output. Keep the temporal, label, and `ohm_relation_id` expectations intact.

Make the failing-test checkpoint explicit. The updated assertion should look more like:

```python
assert period["geojson"]["type"] == "Point"
assert len(period["geojson"]["coordinates"]) == 2
```

This should fail immediately against the current `MultiPolygon` output and makes the contract change unambiguous.

- [ ] **Step 3: Update staged build tests to expect point-only final JSONL**

In `pipeline/tests/test_ohm_borders_stages.py`, update the build-stage expectations so the merged `built/` and `final/` JSONL artifacts show point payloads inside `_geometry_periods` instead of polygons.

The staged pipeline should still preserve:

- `_ohm_relation_id`
- stage ordering
- temporal bounds
- labels
- `external_tags`

- [ ] **Step 4: Run the focused Python tests to verify they fail**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
```

Expected:

- mapper and stage assertions fail because the current code still emits `MultiPolygon`
- the new helper test fails because the representative-point helper does not exist yet

- [ ] **Step 5: Commit the failing-test checkpoint**

```powershell
git add pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py
git commit -m "test: lock OHM point-only mapper contract"
```

### Task 2: Implement Representative-Point Derivation In The OHM Pipeline

**Files:**
- Modify: `pipeline/ohm_borders/fetcher.py`
- Modify: `pipeline/ohm_borders/mapper.py`

- [ ] **Step 1: Add a representative-point helper to `pipeline/ohm_borders/fetcher.py`**

Implement a small helper, for example `derive_representative_point(geometry: dict[str, Any]) -> dict[str, Any] | None`, with this behavior:

- return the geometry unchanged when it is already a `Point`
- for `Polygon` and `MultiPolygon`, use Shapely `representative_point()` as the primary path so the point stays inside the geometry when possible
- if Shapely is unavailable for this helper path, fall back to a deterministic ring-based center using the existing ring helpers already in the file
- prefer the largest available outer ring for the fallback, then use its centroid helper rather than inventing a second polygon traversal strategy
- return `None` when the geometry is missing or unusable

Keep this helper local to the OHM pipeline. Do not broaden it into a generic geospatial abstraction yet.

- [ ] **Step 2: Update `pipeline/ohm_borders/mapper.py` to emit point-only stage payloads**

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

- [ ] **Step 3: Keep transient polygon geometry out of the final JSONL only**

Do not change `parse` artifacts or upstream raw geometry assembly in this pass. The parsed OHM records may still carry stage polygons internally; only the built and final importer-facing JSONL should stop carrying them.

- [ ] **Step 4: Run the focused Python tests to verify they pass**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
```

Expected: PASS.

- [ ] **Step 5: Commit the pipeline implementation checkpoint**

```powershell
git add pipeline/ohm_borders/fetcher.py pipeline/ohm_borders/mapper.py pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py
git commit -m "feat: emit point-only OHM border stage geometry"
```

### Task 3: Lock The Laravel Border Import Contract With Failing Tests

**Files:**
- Modify: `api/tests/Feature/Feature/ImportBordersCommandTest.php`

- [ ] **Step 1: Update fixture records to use point-only `_geometry_periods[*].geojson`**

Replace the existing `MultiPolygon` fixtures in `ImportBordersCommandTest` with point fixtures such as:

```php
'geojson' => [
    'type' => 'Point',
    'coordinates' => [12.5, 41.9],
],
```

Keep the same temporal ranges and relation ids so the importer behavior is compared on equal metadata.

- [ ] **Step 2: Add assertions that imported OHM periods write to `geom`, not `territory_geom`**

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

- [ ] **Step 3: Add assertions that the primary entity location remains point-only**

Assert that the importer still hydrates the entity’s primary location from the first available OHM stage, but now as a point:

- `entity_locations.geom` is populated
- `entity_locations.territory_geom` remains null for this OHM import path

- [ ] **Step 4: Run the focused Laravel test to verify it fails**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected:

- tests fail because the current import job still writes OHM stage payloads to `geometry_periods.territory_geom`

- [ ] **Step 5: Commit the failing importer-test checkpoint**

```powershell
git add api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "test: lock point-only OHM import behavior"
```

### Task 4: Make The Border Importer Persist OHM Period Points Only

**Files:**
- Modify: `api/app/Jobs/ImportBorderEntityJob.php`

- [ ] **Step 1: Change `upsertGeometryPeriods()` to write OHM-imported points into `geom`**

Update the `GeometryPeriod::query()->create([...])` payload so OHM-imported stages set:

```php
'geom' => $geojson,
'territory_geom' => null,
```

instead of the current `territory_geom => $geojson` behavior.

Do the same for any future update-or-reuse branch in this method if a new branch is introduced during implementation.

- [ ] **Step 2: Add a hard guard against polygon regression in the OHM import path**

Before persisting the stage geometry, verify the payload is a point-like geometry for this path. If the payload is unexpectedly polygonal, either skip it with a targeted log entry or fail fast in the narrowest way the existing import conventions allow.

This keeps the importer honest even if a later mapper change accidentally reintroduces polygons.

- [ ] **Step 3: Keep georef creation and representative-point hydration intact**

Do not change:

- `firstOrCreateGeoRef()`
- `attachGeometryPeriodGeoRefs()`
- `syncEntityTemporalBounds()`

Keep `hydrateEntityGeometry()` in place so the primary entity location still gets a base point from the imported OHM stages. Because the mapper now emits point-only stage payloads, the existing hydrator should naturally populate `entity_locations.geom`.

- [ ] **Step 4: Run the focused Laravel test to verify it passes**

Run:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected: PASS.

- [ ] **Step 5: Commit the importer implementation checkpoint**

```powershell
git add api/app/Jobs/ImportBorderEntityJob.php api/tests/Feature/Feature/ImportBordersCommandTest.php
git commit -m "feat: store OHM imported geometry periods as points"
```

### Task 5: Update Operator Docs And Verify The First-Pass Contract End To End

**Files:**
- Modify: `docs/schemas/pipeline-entity-record.md`
- Modify: `pipeline/ohm_borders/README.md`

- [ ] **Step 1: Update the pipeline entity schema doc**

In `docs/schemas/pipeline-entity-record.md`, document that the OHM borders build output keeps `_geometry_periods[*].geojson` as the importer-facing spatial field, but that this first pass now emits a representative `Point` instead of a polygonal OHM border geometry.

Make the note explicit that full OHM polygons remain transient in the pipeline and are no longer persisted through this importer path.

Include the rationale, not just the shape change:

- final JSONL should stay lightweight
- OHM feature identity still lives in `entity_geo_refs`
- representative points still support map markers and reverse lookup
- `territory_geom` stays available for manual or curated local boundary authoring outside this import path

- [ ] **Step 2: Update the OHM borders README**

In `pipeline/ohm_borders/README.md`, add a short section explaining:

- the pipeline still assembles full OHM geometry transiently
- built/final JSONL now carries point-only stage geometry for border imports
- Laravel import still creates `entity_geo_refs` and `geometry_periods`, but OHM-imported periods are point-only in this pass
- local persisted polygons are intentionally deferred to later curated or tile-driven flows

- [ ] **Step 3: Run the focused Python and Laravel checks together**

Run:

```powershell
py -m pytest pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_stages.py -k "geometry or build_stage" -v
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php
```

Expected: both commands pass.

- [ ] **Step 4: Run one smoke build plus sync import using an OHM fixture artifact**

Use an existing small fixture-backed run or temporary artifact directory and run:

```powershell
py -m pipeline borders build --run-id <fixture-run-id> --artifact-dir <fixture-artifact-dir> --force
docker compose -f docker/docker-compose.yml exec app php -d memory_limit=1024M artisan pipeline:import-borders <fixture-jsonl-path> --sync --force --batch-id=ohm-point-first-pass-smoke
```

Expected:

- built JSONL contains point-only `_geometry_periods[*].geojson`
- imported OHM periods have `geom` populated and `territory_geom` empty
- georef rows still exist for the root OHM relation and any stage relations

- [ ] **Step 5: Commit the docs and verification checkpoint**

```powershell
git add docs/schemas/pipeline-entity-record.md pipeline/ohm_borders/README.md
git commit -m "docs: describe point-only OHM border import contract"
```

---

## Handoff Notes For The Next Pass

After this first pass lands, the next migration can decide whether to:

- add an explicit location method for OHM-derived representative points instead of reusing `ohm_nominatim`
- make map and timeline APIs return OHM feature references alongside local points
- stop relying on local `geometry_periods` for OHM border overlays entirely and shift polygon rendering to direct OHM tile highlighting
- add richer point provenance fields when historians need to distinguish representative-point, Wikidata-point, and capital-point strategies

Those are intentionally deferred so the first pass can remain a narrow, reversible contract change.