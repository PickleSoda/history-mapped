# Map Query Optimization Plan

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](STATUS.md).
> **Date:** 2026-06-12
> **Scope:** The geospatial + temporal query that fetches entities for map display.
> **Audit basis:** Read-only GitNexus-guided audit of `api/routes/api.php`, the V1 `EntityController`,
> `MapEntitiesAction`, `MapEntitiesByYearAction`, `ResolveOhmFeatureAction`, `EntityBuilder`, the
> `GeoJson` cast, and all geometry/temporal migrations. Findings independently spot-checked against source.

> **Filename note:** there is a pre-existing `docs/plans/10-ohm-phase-2-timeline-map-interaction.md`.
> This file intentionally reuses the `10-` prefix per the task brief; the two are unrelated. Renumber if the
> duplicate prefix is undesirable.

---

## 1. Headline finding

The map read path is **not** primarily a round-trip problem — it is a **wrong-endpoint + unbounded-payload** problem.

Both map endpoints already issue **exactly one SQL statement per request**, push the bounding-box filter, GeoJSON
serialization (`ST_AsGeoJSON`), and primary-alias resolution **into Postgres**, and stream the result with
`cursor()` + a `StreamedResponse`. GiST indexes already exist on every geometry column. That part is healthy.

The problem is that **the UI calls the wrong endpoint**:

| Endpoint | Handler → Action | bbox? | zoom-aware? | default limit | geometry | Consumer today |
|---|---|---|---|---|---|---|
| `GET /api/v1/entities/map/year` | `EntityController::mapByYear` → `MapEntitiesByYearAction` | **no** | no | **100,000** | full-resolution | **The live dashboard** (`api/resources/js/pages/dashboard.tsx:76`) |
| `GET /api/v1/entities/map` | `EntityController::map` → `MapEntitiesAction` | yes (required) | yes (`ZoomImpactThreshold`) | 2,000 (≤5,000) | full-resolution | **none** |

So the viewport-bounded endpoint the whole project wants **already exists and is fully implemented** — and nothing
calls it. The dashboard instead fetches **every geometry period on Earth for the selected year**, serialized at ~1 m
coordinate precision (`ST_AsGeoJSON(..., 5)`) with **zero simplification**, capped at 100,000 features. Each year
change re-downloads a global multi-MB FeatureCollection. (Confirmed in [MapEntitiesByYearAction.php:22](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L22)
and [:48](../../api/app/Actions/Entity/MapEntitiesByYearAction.php#L48).)

The genuine PHP↔Postgres round-trip waste lives in two **adjacent** paths, not the map render itself:

1. **Map-click resolution** — `ResolveOhmFeatureAction` fires **4–10 sequential queries per click** (a redundant
   `findOrFail` re-fetch of a row it already has, plus a `SELECT ST_AsGeoJSON(?)` round trip per geometry attribute
   via the `GeoJson` cast fallback).
2. **The `/v1/entities` list filters** — `EntityBuilder::inBbox/nearPoint/inTimeRange/existsAt` put a **correlated
   scalar subquery on the left** of the `&&`/comparison operator, which makes every GiST/btree index unusable and
   forces a **full scan of `entities` twice** (the page query and `paginate()`'s COUNT).

Two temporal GiST expression indexes (`gp_active_range_gist_idx`, `etr_active_range_gist_idx`) are **dead weight** —
no query is written in the `int4range(...) @> year` shape they index.

This plan fixes the wrong-endpoint issue, shrinks the payload in-DB, removes the click and list round trips, wakes up
the dead indexes, and lays out a vector-tile target for the customer SPA.

---

## 2. Current request lifecycle (what actually happens)

### Map render (the dashboard's only data fetch)
`api/routes/api.php:25` → `EntityController::mapByYear` → `MapEntitiesByYearAction` builds **one** query over
`geometry_periods JOIN entities`: year-overlap predicate (`start_year <= :year AND (end_year IS NULL OR end_year >= :year)`),
geometry-presence guard, a 7-of-10 `verification_status` whitelist, an inline correlated subquery for the primary alias,
`ST_AsGeoJSON(COALESCE(territory_geom, geom), 5)`, `ORDER BY` territory-first / `display_priority` / years, `LIMIT 100000`,
`->cursor()`. `EntityController::streamFeatureCollection` iterates the LazyCollection inside a `StreamedResponse` and
string-builds each Feature (geometry text passes straight through — no PHP re-parse).
**Total: 1 SQL statement. The cost is payload size and row count, not round trips.**

The `/entities/map` (bbox) path is identical plus the `(territory_geom && ST_MakeEnvelope(...,4326) OR geom && ST_MakeEnvelope(...,4326))`
spatial predicate and a `ZoomImpactThreshold::forZoom` impact floor — and has no caller.

### Map click (most-used interactive flow; the real round-trip offender)
`POST /api/v1/map/resolve-ohm-feature` → `ResolveOhmFeatureAction`: (1) raw match query on `entity_geo_refs JOIN entities`;
(2) `EntityGeoRef::findOrFail` **re-fetches the same row**; (3,4) eager-load `entity` + `entity.primaryLocation`;
(5) optional linked `GeometryPeriod`; (6–7) `SELECT ST_AsGeoJSON(?)` per geometry attribute via the cast fallback;
(8) date-matched `GeometryPeriod` fallback; (9–12) more cast round trips. **Total: 4–10+ statements per click.**

### List with spatial/temporal filters
`GET /v1/entities` → `ListEntitiesAction` → `Entity::query()->withGeoJson()` + `EntityBuilder` filters → `paginate()`:
a COUNT query and a page query, **each** carrying the correlated-subquery bbox/temporal predicate evaluated per
`entities` row (full scan, twice), plus six correlated subqueries per row in the projection. `include_relationships=1`
adds four eager-load queries. **Note:** `parent_id=...` currently throws `BadMethodCallException` before any SQL
(`childrenOf` is undefined) — see the bug report.

---

## 3. Index audit (geometry + temporal)

| Table | Index | State |
|---|---|---|
| `geometry_periods` | `gp_geom_gist_idx` GIST(geom), `gp_territory_geom_gist_idx` GIST(territory_geom) | **Used** by `/entities/map` bbox `&&` (BitmapOr) |
| `geometry_periods` | `gp_year_range_idx` btree(start_year, end_year) | Weak (only the `start_year <=` prefix is usable; the `end_year IS NULL OR …` arm is not) |
| `geometry_periods` | `gp_active_range_gist_idx` GIST(int4range(start_year, end_year+1, '[)')) | **DEAD** — no query uses the `int4range @> :year` shape |
| `entity_locations` | `el_geom_gist_idx`, `el_territory_geom_gist_idx` | **Unusable** from current SQL — correlated subquery sits on the operator's LHS |
| `entity_temporal_ranges` | `etr_active_range_gist_idx` GIST(int4range expr) | **DEAD** — same reason as `gp_active_range_gist_idx` |
| `entity_aliases` | `ea_entity_idx`, `ea_name_idx` | Present; **missing** partial `(entity_id) WHERE is_primary` |
| `entities` | btree on impact_score, entity_type, entity_group, verification_status, composites | Present; **missing** index on `display_priority` (outer sort key, nullable) |
| `entity_geo_refs` | `egr_lookup_idx`, `egr_temporal_year_idx` | Adequate — drives `ResolveOhmFeatureAction`'s match query well |

**Missing / to add:** partial (ideally `UNIQUE`) `(entity_id) WHERE is_primary = true` on `entity_aliases`,
`entity_locations`, `entity_temporal_ranges`; an index on `entities.display_priority`; a `CHECK`/typmod enforcing
**SRID 4326** on all four geometry columns (today 4326 is a write-convention only — one stray-SRID row would make
every `&&` map query throw "mixed SRID" at runtime).

---

## 4. Target query design

### Assumptions
- All stored geometry is SRID 4326 lon/lat (enforced today only by write-path convention; lock it in first — item 11).
- `end_year IS NULL` means "ongoing".
- The bbox endpoint becomes the single map fetch; the client sends `bbox_*`, `year` (or `temporal_start/temporal_end`),
  `zoom_level`, optional `types`/`group`/`min_impact`, `limit`.

### Option A — one set-based GeoJSON query (short-term, drop-in for `MapEntitiesAction`)
Keep everything the current query already pushes down, and make four changes:

1. **Index-usable temporal predicate.** Replace the `start_year <= :y AND (end_year IS NULL OR end_year >= :y)` pair
   with the range-containment form `int4range(start_year, end_year+1, '[)') @> :year` (NULL `end_year` → unbounded
   upper). This is textually identical to the existing `gp_active_range_gist_idx` expression, so that dead index
   becomes live. For range requests, use the range-overlap (`&&`) operator against `int4range(:start, :end+1, '[)')`.
   The range form **fully replaces** the year predicate when a range is supplied — which also fixes the temporal-override
   bug (see §6, bug MQ-1).
2. **Per-entity dedup + corrected ordering.** Wrap as `DISTINCT ON (entity_id)` ordered by entity, then territory-first,
   then recency, inside a subquery; order the outer query by `display_priority DESC NULLS LAST, impact_score DESC NULLS LAST`
   before `LIMIT`. One feature per entity, the LIMIT cut becomes meaningful, and the `NULLS FIRST` priority inversion is fixed.
3. **Zoom-keyed simplification + precision, in-DB.** Project geometry as
   `ST_AsGeoJSON(ST_SimplifyPreserveTopology(COALESCE(territory_geom, geom), :tolerance), :digits)` where `:tolerance`
   (≈ one screen pixel at the requested zoom, derived server-side from `zoom_level`) and `:digits` (3 at zoom ≤5, 4 at
   6–9, 5 at ≥10) come from the zoom band; guard points from simplification. **This is the single biggest payload lever.**
4. **Alias lookup via `LEFT JOIN LATERAL`** on `entity_aliases` (backed by the new partial `is_primary` index) instead of
   the correlated `COALESCE` subquery; apply the currently-ignored `entity_group` filter here too.

The controller keeps `cursor()` + `StreamedResponse`: still **1 SQL statement per request**, now with a deduplicated,
zoom-simplified, viewport-bounded payload. Optionally have Postgres assemble whole Feature objects
(`jsonb_build_object(...)`) so PHP only concatenates rows.

### Option B — `ST_AsMVT` vector tiles (target architecture for the customer SPA)
Add `GET /v1/tiles/{z}/{x}/{y}?year=&types=&min_impact=` returning `application/x-protobuf`, **one SQL statement per tile**:
- a `bounds` CTE from `ST_TileEnvelope(:z,:x,:y)` (and its 4326 transform for the `&&` prefilter);
- a `mvtgeom` CTE selecting `ST_AsMVTGeom(ST_Transform(COALESCE(territory_geom, geom), 3857), bounds.env, 4096, 256, true)`
  plus entity columns, with the `int4range` temporal predicate, the zoom-band impact filter, and `DISTINCT ON (entity_id)` dedup;
- a final `SELECT ST_AsMVT(mvtgeom, 'entities', 4096, 'geom')`.

Simplification is implicit in the MVT grid quantization, payloads become KB-scale, and tiles are immutable per
`(z,x,y,year-band,filters)` — ideal for HTTP/CDN caching because map data only changes on import.

### Round trips / payload removed by this design
| Path | Before | After |
|---|---|---|
| Map render | 1 query, **global** full-res payload (≤100k features) | 1 query, **viewport** simplified payload (−90%+ at country/region zoom) |
| Map click (`resolve-ohm-feature`) | 4–10 sequential queries | **1** query |
| List `/v1/entities` (bbox/temporal) | 2 full `entities` scans (6 w/ relationships) | index-driven scans of matching rows |
| Backfill / import geometry | O(entities × ranges × relationships) round trips + WKB→JSON→WKB | constant per batch, geometry stays column-to-column in Postgres |

---

## 5. Prioritized backlog

Ordering reflects dependencies, risk, and payoff: the biggest user-visible win (stop fetching the globe) and the
cheapest payload lever come first; correctness/index plumbing that the later items depend on comes next; the
vector-tile rewrite is last because it depends on SRID enforcement and the dedup/index work. **All blast radii are
GitNexus `impact(upstream)` results; every map symbol resolves to LOW risk with a single direct dependent
(`EntityController`), because Eloquent builder dispatch and `fetch()`→route edges are not captured in the graph —
manually source-verified.**

### P1 — Point the live map UI at the bbox endpoint (with viewport + zoom) · effort M · LOW
Change `dashboard.tsx` (and any future `web/` SPA map) to call `GET /v1/entities/map` with `bbox` from `map.getBounds()`,
`zoom_level` from `map.getZoom()`, and `year`, refetching on **debounced** `moveend`/`zoom`. Keep `/map/year` only as an
explicit "global overview" mode with a bounded default limit and a default zoom-band `min_impact`.
**Prerequisite correctness fixes in `MapEntitiesAction` first:** temporal-override (MQ-1), apply `group` (MQ-2),
`NULLS LAST` ordering (MQ-7).
**Impact:** fetched rows go from "every period on Earth for the year" to viewport-bounded; `ZoomImpactThreshold`
finally takes effect for the real UI; ≥90% payload reduction at country/region zoom even before simplification.
**Touches:** `api/resources/js/pages/dashboard.tsx`, `dashboard.test.tsx` (pins the current `/map/year` URL), `MapEntitiesAction`.

### P2 — Zoom-keyed in-DB geometry simplification + precision · effort S · LOW
Wrap the geometry projection in both map actions as `ST_AsGeoJSON(ST_SimplifyPreserveTopology(COALESCE(territory_geom, geom), :tolerance), :digits)`,
tolerance ≈ one pixel at the request's zoom, digits 3–5 by band; guard points. Pure SQL change inside the existing single statement.
**Impact:** polygon payload −80 to −95% at world/continent zoom (full-res OHM borders at 5 decimals are the dominant cost). Output shape unchanged → frontend untouched.
**Prereq:** P1 (zoom must reach the server; already validated on `/entities/map`).

### P3 — Collapse `ResolveOhmFeatureAction` into one statement (4–10 → 1) · effort M · LOW
One SQL with a CTE picking the best geo-ref (existing ORDER BY), `LEFT JOIN LATERAL` the linked period, the
date-matched fallback period (treating `end_year IS NULL` as ongoing — also fixes MQ-8), and the primary
`entity_location`; project `ST_AsGeoJSON(COALESCE(...))` and a computed `resolution_source`. Drops the `findOrFail`
re-fetch and all cast-fallback round trips.
**Impact:** queries per click 4–10 → 1; click-to-highlight latency drops by the eliminated round trips.
**Prereq:** none (`egr_lookup_idx` + `gp` indexes already support it). Coordinate with `ResolveOhmFeatureApiTest`.

### P4 — Rewrite `EntityBuilder` spatial/temporal filters as `EXISTS`/`LATERAL` · effort M · LOW
Replace the correlated-scalar-subquery predicates (`inBbox`, `territoryInBbox`, `nearPoint`, `orderByDistanceFrom`,
`inTimeRange`, `existsAt`) with `EXISTS (... WHERE el.geom && ST_MakeEnvelope(...))` / `JOIN LATERAL`, putting the
indexed column on the operator's LHS; convert `withGeoJson()`'s six per-row scalar subqueries into `LEFT JOIN LATERAL` probes.
**Impact:** bbox-filtered list queries go from full `entities` scans (twice) to GiST-driven index scans — O(matching rows)
instead of O(table).
**Prereq:** P5 (partial `is_primary` indexes make the lateral probes cheap). Also touches `GenerateEntityEmbeddingJob` (uses `withGeoJson`).

### P5 — Add partial (ideally `UNIQUE`) `is_primary` indexes · effort S · LOW
Migration: `CREATE [UNIQUE] INDEX ... ON entity_aliases (entity_id) WHERE is_primary = true` (and the same on
`entity_locations`, `entity_temporal_ranges`).
**Impact:** per-row alias/location/temporal probes become single index lookups; removes the inner `ORDER BY updated_at`
sorts; the `UNIQUE` variant codifies the one-primary-per-entity invariant the code already assumes everywhere.
**Prereq:** run a duplicate-primary audit first if choosing `UNIQUE` (it would fail on dirty data).

### P6 — Align temporal predicates with the `int4range` GiST indexes · effort S · LOW
Rewrite the year/range predicates in both map actions (and the temporal `EntityBuilder` filters) into the
`int4range(start_year, end_year+1, '[)') @> :year` / `&&` form so `gp_active_range_gist_idx` and
`etr_active_range_gist_idx` finally match — or add a stored generated `active_range int4range` column + GiST and drop
the expression indexes.
**Impact:** `/map/year` goes from a seq-scan of `geometry_periods` to a GiST range scan; bbox queries gain a second
indexable dimension; two dead indexes start earning their write cost (or get dropped).
**Prereq:** none for the predicate rewrite; migration for the generated-column variant. Verify with `EXPLAIN`.

### P7 — Per-entity dedup + corrected ordering (`DISTINCT ON`) · effort S · LOW
Wrap the map query as `DISTINCT ON (entity_id)` ordered by entity / territory-first / recency, then outer-order by
`display_priority DESC NULLS LAST, impact_score DESC NULLS LAST` before `LIMIT`. Fixes duplicate features (MQ-9) and
the `NULLS FIRST` priority inversion (MQ-7) in one change.
**Prereq:** none. Coordinate with `GeometryPeriodPrecedenceTest`. **Open question:** confirm one-feature-per-entity is the desired contract (§7).

### P8 — Trim map feature properties + emit `entity_color` from SQL · effort S · LOW
Reduce `properties` to what the UI consumes (`id`, `name`, `entity_type`, `entity_group`, `impact_score`, `start_year`,
`end_year`) plus `attributes->>'entity_color' AS entity_color`; drop `display_priority`/`icon_class`/`period_type`/
`geometry_period_id` from the payload unless a consumer is identified. Realign the `MapFeature` TS type and the viewer
popup keys to the same contract (fixes MQ-6 / the frontend contract-drift bug).
**Impact:** properties payload −30–50% per feature; entity colors finally render; one honest typed contract.
**Prereq:** P1 (same frontend files). Add a feature-shape contract test.

### P9 — HTTP caching for map responses · effort S · LOW
Add `Cache-Control` + an `ETag` derived from `(max(geometry_periods.updated_at), filters)` (or a data-version counter
bumped by import jobs) so browsers/CDN serve repeat year/viewport requests as 304s. Map data changes only on import/admin edit.
**Prereq:** P1–P2 (stable parameterization worth caching) + a data-version source.

### P10 — `ST_AsMVT` vector-tile endpoint for the customer map · effort L · n/a (new code)
Add `GET /v1/tiles/{z}/{x}/{y}` per Option B; serve protobuf with long-lived cache headers; render via a MapLibre
vector source. Keep the GeoJSON endpoint for ad-hoc API consumers.
**Impact:** KB-scale payloads regardless of geometry complexity; immutable, CDN-cacheable tiles; still 1 SQL/tile.
**Prereq:** P11 (SRID enforcement — `ST_Transform` needs known SRID), P5–P7, plus MapLibre source/layer rework.

### P11 — Enforce SRID 4326 on all geometry columns · effort S · LOW
Migration adding `CHECK (geom IS NULL OR ST_SRID(geom) = 4326)` (and `territory_geom`) on `geometry_periods` and
`entity_locations`, or convert to `geometry(Geometry,4326)` typmod.
**Impact:** eliminates a class of runtime 500s on the primary map path; hard prerequisite for MVT.
**Prereq:** audit existing rows (`SELECT DISTINCT ST_SRID(...)`) first; all audited write paths already use
`ST_SetSRID(...,4326)`, so it should be a no-op on clean data.

### P12 — Set-based rewrite of geometry backfill/import loops · effort M · LOW
Replace `BackfillGeometryPeriodsAction`'s per-range/per-relationship `create()` loops and the PHP GeoJSON intermediate
with `INSERT ... SELECT` statements that copy geometry column-to-column inside Postgres; batch
`ImportBorderEntityJob`'s period upserts with `INSERT ... ON CONFLICT`.
**Impact:** backfill round trips collapse from O(entities × ranges × relationships) to a constant per batch; removes
the WKB→JSON→WKB conversion. Batch path only — zero request-path risk.

---

## 6. Correctness bugs blocking P1 (cross-reference)
These live in the consolidated [12-bug-report.md](12-bug-report.md); they must be fixed as part of P1 because they make
the bbox endpoint wrong rather than just slow:

- **MQ-1 (high):** `temporal_start/temporal_end` is ANDed with a hidden default `year=1000` instead of overriding it →
  range requests return almost nothing.
- **MQ-2 (medium):** the validated `group` filter is silently ignored by both map actions.
- **MQ-7 (medium):** `ORDER BY display_priority DESC` sorts NULL-priority rows first (Postgres `NULLS FIRST`), so
  un-prioritized entities crowd out curated ones under `LIMIT`.
- **MQ-9 (low):** duplicate features per entity when multiple periods cover the year.
- **MQ-8 (medium):** `ResolveOhmFeatureAction` excludes open-ended periods (`end_year IS NULL`) — fixed by P3.

---

## 7. Open questions for the owner
1. **Which endpoint should the customer `web/` SPA map consume?** The bbox/zoom GeoJSON path (P1–P2) or jump straight to
   MVT tiles (P10)? This decides how much to invest in the GeoJSON path.
2. **Is the silent default `year=1000` on `/entities/map` intentional?** It is test-pinned
   (`MapEntitiesYearFilteringTest::test_default_year_is_1000_when_not_provided`) but surprising for API consumers.
3. **Is one-feature-per-entity the desired map contract?** Or are simultaneous period geometries (territory + presence)
   intentionally rendered as separate features? This decides whether P7's `DISTINCT ON` is a fix or a regression.
4. **Should the one-primary-per-entity invariant be DB-enforced** (`UNIQUE` partial indexes, P5)? Code assumes it; nothing prevents duplicates today.
5. **Does the product need antimeridian-crossing viewports** (Pacific-centric maps)? If yes, bbox normalization/splitting must precede P1.
6. **Where do polygon territory geometries in `geometry_periods` come from at scale?** `ImportBorderEntityJob` rejects
   non-Point geometry and routes polygons to `entity_locations.territory_geom` instead; only the admin editor and
   `BackfillGeometryPeriodsAction` write polygons to `geometry_periods`. The payoff of P2 depends on how many real
   border polygons actually land there.
