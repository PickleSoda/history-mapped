# Map Bounding-Box Query Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live map fetch only the viewport at zoom-appropriate resolution via one correct set-based query, fix the map-path correctness bugs, and collapse the map-click resolver to a single statement.

**Architecture:** Repoint `dashboard.tsx` at the existing bbox endpoint; rewrite `MapEntitiesAction` (and align `MapEntitiesByYearAction`) for correctness + `DISTINCT ON` dedup + zoom simplification + index-usable predicates; add supporting migrations; collapse `ResolveOhmFeatureAction`; rewrite `EntityBuilder` spatial/temporal filters as `EXISTS`/`LATERAL`.

**Tech Stack:** Laravel 13 (PHP 8), PostgreSQL 16 + PostGIS, PHPUnit; React 19 + MapLibre GL v5 + TanStack Query (Vitest).

**Spec:** [../specs/2026-06-12-map-bbox-query-optimization-design.md](../specs/2026-06-12-map-bbox-query-optimization-design.md)

---

## File structure

| File | Change |
|------|--------|
| `api/app/Actions/Entity/MapEntitiesAction.php` | Rewrite query: confidence, temporal-override, group, simplify, dedup, ordering, COALESCE filter, antimeridian, alias lateral, property trim |
| `api/app/Actions/Entity/MapEntitiesByYearAction.php` | Same correctness + bounded default limit/min_impact |
| `api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php` | Single-statement rewrite |
| `api/app/Builders/EntityBuilder.php` | EXISTS/LATERAL filters; remove/fix `childrenOf` |
| `api/app/Http/Api/V1/Requests/MapEntitiesRequest.php` | Require year-or-range; relax lng bounds |
| `api/app/Http/Api/V1/Controllers/EntityController.php` | ETag/Cache-Control; drop `children` eager-load (or implement) |
| `api/database/migrations/2026_06_12_*` | partial UNIQUE is_primary; functional GiST; display_priority index |
| `api/resources/js/pages/dashboard.tsx` | bbox/zoom/debounce/abort; MapFeature contract; keep viewer mounted |
| Tests | `api/tests/Feature/Api/*`, `api/resources/js/pages/__tests__/dashboard.test.tsx` |

> Run PHP via `docker compose -f docker/docker-compose.yml exec app php artisan test --filter=<name>`; JS via `pnpm --filter <admin> test`.

---

## Phase 1 — Map-action correctness

### Task 1: Fix the inverted confidence filter (LC-1)

**Files:** Modify `MapEntitiesAction.php:106`, `MapEntitiesByYearAction.php:86`; Test `api/tests/Feature/Api/MapEntitiesConfidenceTest.php` (new)

- [ ] **Step 1: Write the failing test** — seed entities with `high` and `low` confidence; `GET /v1/entities/map?...&min_confidence=medium` returns the `high` one and excludes `low`.
- [ ] **Step 2: Run → FAIL** (today it returns low/unresolved). `... php artisan test --filter=MapEntitiesConfidenceTest`
- [ ] **Step 3: Implement** — replace the raw `where('entities.confidence','>=',$v)` with `->whereIn('entities.confidence', ConfidenceLevel::atLeast($level))` where `atLeast` returns the upward slice of `[unresolved, low, medium, high]`; add that helper to `ConfidenceLevel` (mirroring `EntityBuilder::withMinConfidence`). Apply in both actions.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): correct min_confidence filter on map endpoints (was inverted by PG enum order)`

### Task 2: Temporal range overrides the default year (MQ-1)

**Files:** Modify `MapEntitiesAction.php:66-116`; Test `MapEntitiesYearFilteringTest.php`

- [ ] **Step 1: Write the failing test** — `GET /v1/entities/map?bbox...&temporal_start=1500&temporal_end=1600` returns a 1550-only period and does NOT require coverage of year 1000.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — only add the single-year predicate when no `temporal_start/temporal_end` is present; require `year` OR a range in `MapEntitiesRequest` (422 otherwise) and remove the `resolveYear` default of 1000.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): temporal range replaces (not ANDs) the year filter on map endpoint`

### Task 3: Apply the `group` filter (MQ-13)

**Files:** Modify `MapEntitiesAction.php`; Test `MapEntitiesFilterTest.php` (new)

- [ ] **Step 1: Write the failing test** — `...&group=POLITY` excludes a PLACE entity.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `if (isset($filters['group'])) $query->where('entities.entity_group', EntityGroup::from($filters['group'])->value);`
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): apply validated group filter on map endpoint`

### Task 4: `DISTINCT ON` dedup + NULLS-LAST ordering (MQ-15, MQ-16)

**Files:** Modify both map actions; Test `GeometryPeriodPrecedenceTest.php`, `MapEntitiesDedupTest.php` (new)

- [ ] **Step 1: Write the failing tests** — (a) an entity with two periods covering the year yields ONE feature; (b) a curated `display_priority` entity outranks a NULL-priority one under a small `limit`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — wrap the query as `DISTINCT ON (entities.entity_id)` with an inner `ORDER BY entity_id, (territory_geom IS NULL), start_year DESC, end_year ASC NULLS FIRST`, then outer `ORDER BY display_priority DESC NULLS LAST, impact_score DESC NULLS LAST`; add an `?all_periods=1` bypass.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): one feature per entity on map; NULLS-LAST priority ordering`

---

## Phase 2 — Indexes + index-usable predicates

### Task 5: Migration — partial UNIQUE is_primary, functional GiST, display_priority

**Files:** Create `api/database/migrations/2026_06_12_000001_map_optimization_indexes.php`; Test `MapIndexMigrationTest.php` (new)

- [ ] **Step 1: Write a dedup-audit query** in the migration's `up()` guard: abort with a clear message if any `(entity_id) WHERE is_primary` duplicates exist (so the UNIQUE creation can't fail mid-deploy).
- [ ] **Step 2: Write the migration** — `CREATE UNIQUE INDEX ... ON entity_aliases (entity_id) WHERE is_primary` (and entity_locations, entity_temporal_ranges); `CREATE INDEX gp_map_geom_gist ON geometry_periods USING GIST (COALESCE(territory_geom, geom))`; `CREATE INDEX entities_display_priority_idx ON entities (display_priority DESC NULLS LAST)`.
- [ ] **Step 3: Run migrations on a test DB** — `... php artisan migrate --env=testing` → success; the audit guard passes on seed data.
- [ ] **Step 4: Commit** `feat(api): map-optimization indexes (partial unique is_primary, functional GiST, display_priority)`

### Task 6: int4range temporal predicate (MQ-7)

**Files:** Modify both map actions; Test `MapEntitiesYearFilteringTest.php`

- [ ] **Step 1: Write/extend the test** — boundary years (period 900–1100 matches 1000; 1200–1300 excludes 1000) still pass after the rewrite, AND an `EXPLAIN` test asserts `gp_active_range_gist_idx` is used.
- [ ] **Step 2: Run → FAIL** (EXPLAIN shows no GiST use today).
- [ ] **Step 3: Implement** — replace the scalar predicate with `whereRaw("int4range(geometry_periods.start_year, CASE WHEN geometry_periods.end_year IS NULL THEN NULL ELSE geometry_periods.end_year + 1 END, '[)') @> ?", [$year])`; range form uses `&&`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `perf(api): use int4range GiST index for map temporal predicate`

---

## Phase 3 — Payload: simplification, COALESCE filter, antimeridian, property trim

### Task 7: Zoom-keyed simplification + precision (MQ-6)

**Files:** Modify `MapEntitiesAction.php:62`; add `api/app/Services/ZoomSimplification.php`; Test `MapEntitiesSimplifyTest.php` (new)

- [ ] **Step 1: Write the failing test** — a dense polygon returned at low zoom has fewer vertices than at high zoom.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `ZoomSimplification::forZoom($z): ['tolerance'=>..., 'digits'=>...]`; wrap geometry as `ST_AsGeoJSON(ST_SimplifyPreserveTopology(COALESCE(...), :tol), :digits)` guarding points (`ST_Dimension = 0`).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `perf(api): zoom-keyed in-DB geometry simplification`

### Task 8: COALESCE filter/serialize parity + antimeridian (MQ-9, MQ-17)

**Files:** Modify `MapEntitiesAction.php:119-130`, `MapEntitiesRequest.php:32-35`; Test `MapEntitiesBboxTest.php` (new)

- [ ] **Step 1: Write the failing tests** — (a) a feature selected by point but whose territory is off-viewport is not returned (filter matches the serialized geometry); (b) a `min_lng > max_lng` (dateline) viewport returns features on both sides.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — filter on `COALESCE(territory_geom, geom) && ST_MakeEnvelope(...)`; normalize lng to [-180,180] and OR two envelopes when `min>max`; relax the validation `between` to accept wrapped lng and normalize in the action.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): single-geometry bbox filter + antimeridian handling`

### Task 9: Trim feature properties + emit entity_color (MQ-8)

**Files:** Modify both map actions; Test `MapEntitiesFeatureShapeTest.php` (new)

- [ ] **Step 1: Write the failing test** — the feature `properties` contain exactly `{id,name,entity_type,entity_group,impact_score,start_year,end_year,entity_color}` and `entity_color` is populated.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — drop `display_priority`/`icon_class`/`period_type`/`geometry_period_id` from the payload; add `attributes->>'entity_color' AS entity_color` to the projection and the properties map.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): trim map feature properties and emit entity_color`

### Task 9b: Borders-from-OHM — emit the OHM ref + serialize point for OHM-linked entities

**Files:** Modify both map actions (projection + properties); Test `MapEntitiesOhmRefTest.php` (new)

> Spec §3.1. This task covers only the **map-query projection**. The storage-side changes (stop hydrating OHM polygons into `entity_locations.territory_geom`, stop backfill copying `territory_geom`, optional cleanup migration) are **Phase 7** of this plan / decision D19.

- [ ] **Step 1: Write the failing test** — for an entity with an active `ohm`/`relation` geo-ref, the map feature `properties` include `ohm_provider`/`ohm_external_type`/`ohm_external_id`, and its `geometry` is the **point** (`geom`), not a polygon.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `LEFT JOIN LATERAL` the entity's active `ohm` geo-ref (provider=ohm, is_active) into the map query; add `ohm_external_id` (+ provider/type) to the projection and the `properties` map. For rows that have an OHM ref, serialize `ST_AsGeoJSON(geom, …)` (point) rather than `COALESCE(territory_geom, geom)`; non-OHM rows keep `COALESCE(...)` so app-owned polygons still render. Keep the geometry-presence guard so an OHM entity with no stored point is still emitted (geometry may be null + an OHM ref present).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): emit OHM feature ref and serialize point for OHM-linked map entities`

> **Note for Task 7 (simplification):** with borders-from-OHM, country polygons are no longer serialized, so zoom-keyed simplification now applies only to retained **app-owned** polygons — keep Task 7 but treat it as lower priority than this task for payload reduction.

> **Frontend follow-up (sub-project A Phase 4 / a viewer ticket):** use the new `ohm_external_id` property to highlight the matching OHM basemap feature on selection instead of drawing a stored polygon overlay.

---

## Phase 4 — Frontend repoint

### Task 10: Dashboard uses the bbox endpoint with debounce + abort

**Files:** Modify `api/resources/js/pages/dashboard.tsx:71-90,150-165`; Test `dashboard.test.tsx`

- [ ] **Step 1: Update the failing test** — assert one debounced fetch to `/v1/entities/map?bbox_*&zoom_level=&year=` after rapid typing, and that the queryFn receives/forwards `signal`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — compute bbox from `map.getBounds()` and zoom from `map.getZoom()` (lift these via a viewer callback prop `onViewportChange`); debounce the committed year/viewport (~300 ms); pass `signal` into `fetch`; raise `staleTime`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): dashboard fetches viewport bbox with debounce + abort`

### Task 11: Keep the viewer mounted on empty/error years + fix MapFeature type (FE-3, MQ-8)

**Files:** Modify `dashboard.tsx:193-217,21-35`; Test `dashboard.test.tsx`

- [ ] **Step 1: Write the failing test** — an empty-year response keeps `HistoricalMapViewer` mounted (overlay message), not unmounted.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — render the viewer whenever data has ever loaded; pass `[]` for empty years; overlay the message; align `MapFeature.properties` to the Task 9 contract.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(web): keep map mounted across empty/error years; align feature contract`

---

## Phase 5 — Map-click resolver + EntityBuilder

### Task 12: Single-statement `ResolveOhmFeatureAction` (MQ-3, MQ-11)

**Files:** Modify `api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php`; Test `ResolveOhmFeatureApiTest.php`

- [ ] **Step 1: Write/extend the failing tests** — (a) a click resolves with one DB statement (assert via `DB::listen` query count = 1); (b) an entity with only an open-ended period (`end_year IS NULL`) resolves its period geometry, not the point fallback.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — one query: CTE selecting the best geo-ref (existing ORDER BY), `LEFT JOIN LATERAL` best linked period, `LEFT JOIN LATERAL` best date-matched period with `(end_year IS NULL OR end_year >= :year)`, `LEFT JOIN LATERAL` primary location; project `ST_AsGeoJSON(COALESCE(period.territory_geom, period.geom, loc.territory_geom, loc.geom))` + a `CASE` `resolution_source`. Remove the `findOrFail` re-fetch and cast round-trips.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `perf(api): resolve OHM feature in a single statement; include open-ended periods`

### Task 13: EntityBuilder EXISTS/LATERAL + remove/fix childrenOf (MQ-4, MQ-14)

**Files:** Modify `api/app/Builders/EntityBuilder.php:87-164,263-332`, `ListEntitiesAction.php:86`, `EntityController.php:118-119`, `EntityResource.php:88-90`, `ListEntitiesRequest.php:64`; Test `ListEntitiesSpatialTest.php` (new), `ListEntitiesApiTest.php`

- [ ] **Step 1: Write failing tests** — (a) `EXPLAIN` for `GET /v1/entities?bbox...` shows a GiST index scan on `entity_locations`, not a seq scan of `entities`; (b) `GET /v1/entities?parent_id=<uuid>` returns 200 (or 422), never 500.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — rewrite `inBbox`/`territoryInBbox`/`nearPoint`/`orderByDistanceFrom`/`inTimeRange`/`existsAt` as `whereExists`/`JOIN LATERAL` with the indexed column on the left; convert `withGeoJson` subqueries to laterals. Remove `parent_id`/`include_children`/`children` from request/action/controller/resource (decision: hierarchy not implemented now), or implement a `children()` relation + `childrenOf` scope.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `perf(api): index-driven EntityBuilder spatial/temporal filters; remove dead childrenOf`

---

## Phase 6 — Caching

### Task 14: ETag/Cache-Control on map responses

**Files:** Modify `EntityController.php:73-101`; Test `MapEntitiesCacheTest.php` (new)

- [ ] **Step 1: Write the failing test** — a repeat request with `If-None-Match` of the prior `ETag` returns 304.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — compute `ETag` from `max(geometry_periods.updated_at)` + the request filters (one cheap aggregate or a cached data-version counter bumped by import jobs); add `Cache-Control: public, max-age`; short-circuit to 304 on match.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `perf(api): ETag/Cache-Control for map responses`

---

## Phase 7 — Borders-from-OHM storage policy (Laravel import/backfill)

> Spec §3.1 / decision D19. These are the **storage-side** companion changes to Task 9b: stop the heavy border polygons from ever being stored. They live in the Laravel OHM-borders import path (not the Python agent).

### Task 15: Hydrate only points from OHM geo-refs

**Files:** Modify `api/app/Actions/EntityGeoRef/HydrateEntityGeometryFromGeoRefAction.php:25-28`; Test `HydrateEntityGeometryTest.php` (new/extend)

- [ ] **Step 1: Write the failing test** — hydrating from a Polygon OHM geojson leaves `entity_locations.territory_geom` null (only point `geom` is set); a Point still hydrates `geom`.
- [ ] **Step 2: Run → FAIL** (today Polygon → `territory_geom`).
- [ ] **Step 3: Implement** — when `type ∈ {Polygon, MultiPolygon}`, skip the territory write (or derive a representative `ST_PointOnSurface` into `geom`); keep the geo-ref link intact. Gate behind a config flag `borders.store_polygons=false` so the behavior is reversible.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): stop hydrating OHM border polygons into entity_locations (borders-from-OHM)`

### Task 16: Backfill produces point/presence geometry only

**Files:** Modify `api/app/Actions/Entity/BackfillGeometryPeriodsAction.php:65,93,159,173`; Test `BackfillGeometryPeriodsTest.php`

- [ ] **Step 1: Write the failing test** — backfilling an entity whose primary location has a `territory_geom` produces periods with `territory_geom` null (point-only) when `borders.store_polygons=false`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — pass `null` for `territory_geom` in the created periods when the flag is off (keep `geom`); leave the flag-on path unchanged for app-owned data.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): backfill stops copying border polygons into geometry_periods`

### Task 17: Optional cleanup migration — null OHM-derived territory polygons

**Files:** Create `api/database/migrations/2026_06_12_000003_null_ohm_territory_geom.php`; Test `MapIndexMigrationTest.php` (extend)

- [ ] **Step 1: Write the migration** — for entities with an active `ohm` geo-ref, set `entity_locations.territory_geom = NULL` and `geometry_periods.territory_geom = NULL` (keep `geom`); reversible-safe `down()` is a no-op with a logged warning (the polygons came from OHM and can be re-hydrated).
- [ ] **Step 2: Run on a test DB** — `... artisan migrate`; assert storage drops and OHM-linked entities still have a point.
- [ ] **Step 3: Commit** `chore(api): null OHM-derived stored territory polygons (reclaim storage)`

---

## Self-review (coverage)

- LC-1 → T1. MQ-1 → T2. MQ-13 → T3. MQ-15/16 → T4. indexes → T5. MQ-7 → T6. MQ-6 → T7. MQ-9/17 → T8. MQ-8 → T9. borders-from-OHM map query → T9b; storage side → T15–T17 (D19). FE (abort/debounce/mount) → T10/T11. MQ-3/11 → T12. MQ-4/14 → T13. caching → T14. MQ-18 (`include_territories`) → fold into T9 (implement or drop the rule). MQ-19 (backfill ping-pong) → tracked in plan 10 P12, **not** in this plan (batch path, separate). MVT + SRID → **deferred** (separate future spec). **All in-scope spec items mapped.**

## Execution handoff

Recommended: subagent-driven, one task per subagent, review between. Phases 1–2 (correctness + indexes) should land before Phase 4 repoints the UI, so the live map switches onto an already-correct endpoint.
