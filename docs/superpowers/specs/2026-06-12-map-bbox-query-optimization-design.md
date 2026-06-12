# Map Bounding-Box Query Optimization — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (approved) — ready for implementation planning
> **Area:** `api/` (Laravel) + `api/resources/js` (admin map UI)
> **Source:** [../../plans/10-map-query-optimization.md](../../plans/10-map-query-optimization.md) and bug report MQ-1…MQ-19, LC-1.
> **Sub-project:** A of the audit-remediation set.

## 1. Problem

The map read path is healthy on round-trips (one SQL statement) but wrong on **which endpoint the UI uses** and on
**payload size**: the live dashboard calls `/entities/map/year` (no bbox, limit 100 000, full-resolution geometry — a
global multi-MB payload per year change), while the bbox/zoom-aware `/entities/map` endpoint is fully implemented,
indexed, and **unused**. The bbox endpoint also carries correctness bugs that must be fixed before it can become primary,
and the map-click resolver does 4–10 round trips per click.

## 2. Goals / Non-goals

**Goals**
- The live map fetches only the **viewport**, at **zoom-appropriate** resolution, via one set-based query.
- Correctness bugs on the map path are fixed (confidence filter, temporal override, `group`, ordering, dedup, `childrenOf`).
- The map-click resolver runs in one statement.
- The spatial/temporal indexes that exist are actually used.

**Non-goals (deferred / elsewhere)**
- MVT vector tiles — designed but **deferred** until a customer SPA and real row counts justify it (decision: GeoJSON-first).
- Temporal-bound *semantics* (open-ended/BCE) — **sub-project E** (this spec only adjusts the predicate *form* to use the index).

## 3. Accepted decisions

- **Endpoint:** repoint the dashboard at `/entities/map` (bbox + zoom + year), debounced on `moveend`/`zoom`; keep
  `/map/year` only as a bounded "overview" mode. MVT deferred.
- **`year` param:** require `year` (or a range) on `/entities/map`; the silent `year=1000` default is removed there.
- **Dedup:** one feature per entity (`DISTINCT ON`), with an `?all_periods=1` opt-out.
- **OR-bbox:** fix to a single `COALESCE(territory_geom, geom)` expression + functional GiST index.
- **one-primary invariant:** enforce with partial `UNIQUE` indexes (after a dedup audit).
- **antimeridian:** include longitude normalization + two-envelope OR in the bbox work.

## 4. Architecture

```
  dashboard.tsx ──(bbox,zoom,year; debounced; AbortSignal)──► GET /v1/entities/map
        │                                                          │
        │                                              EntityController::map
        │                                              → MapEntitiesAction (single SELECT)
        │                                                  • DISTINCT ON (entity_id)
        │                                                  • int4range temporal predicate (uses GiST)
        │                                                  • ST_SimplifyPreserveTopology keyed to zoom
        │                                                  • COALESCE(territory_geom,geom) filter+serialize
        │                                                  • LEFT JOIN LATERAL primary alias
        │                                                  • group/confidence/min_impact filters (correct)
        │                                                  • ORDER BY display_priority DESC NULLS LAST
        │                                              → streamFeatureCollection (cursor + ETag)
        │
        └─ click ─► POST /v1/map/resolve-ohm-feature → ResolveOhmFeatureAction (ONE statement: CTE + LATERAL joins)
```

### 4.1 Components

**`MapEntitiesAction` (the core query).** A single `DISTINCT ON (entity_id)` SELECT over `geometry_periods JOIN entities`:
- Temporal predicate rewritten to `int4range(start_year, end_year+1, '[)') @> :year` (and `&&` for ranges) so
  `gp_active_range_gist_idx` is used; the range form **replaces** the year predicate when a range is supplied (fixes MQ-1).
- Apply the `entity_group` filter (fixes MQ-13) and fix `min_confidence` to a `whereIn` over the correct enum slice
  (fixes LC-1) — or delegate to `EntityBuilder::withMinConfidence`.
- Geometry: `ST_AsGeoJSON(ST_SimplifyPreserveTopology(COALESCE(territory_geom, geom), :tolerance), :digits)` with
  tolerance/digits derived from `zoom_level`; points guarded from simplification (MQ-6).
- Spatial filter + serialization both on `COALESCE(territory_geom, geom)` against `ST_MakeEnvelope(...,4326)` with a
  functional GiST index; antimeridian handled by normalizing lng and OR-ing two envelopes when `min>max` (MQ-9, MQ-17).
- Primary alias via `LEFT JOIN LATERAL` on `entity_aliases` (MQ-5).
- `ORDER BY display_priority DESC NULLS LAST, impact_score DESC NULLS LAST` (MQ-15); `DISTINCT ON (entity_id)` dedup (MQ-16).
- Properties trimmed to what the UI consumes + `entity_color` from `attributes->>'entity_color'` (MQ-8).

**`MapEntitiesByYearAction`.** Apply the same confidence/ordering fixes; give it a bounded default limit and a default
zoom-band `min_impact`; keep it as an explicit overview endpoint.

**`ResolveOhmFeatureAction`.** Collapse to one statement: CTE for the best geo-ref, `LEFT JOIN LATERAL` the linked +
date-matched periods (treating `end_year IS NULL` as ongoing — MQ-11) and the primary location; project
`ST_AsGeoJSON(COALESCE(...))` + a computed `resolution_source` (MQ-3).

**`EntityBuilder`.** Rewrite `inBbox`/`territoryInBbox`/`nearPoint`/`orderByDistanceFrom`/`inTimeRange`/`existsAt` as
`EXISTS`/`JOIN LATERAL` with the indexed column on the operator's left; convert `withGeoJson`'s six per-row subqueries to
laterals (MQ-4). Remove or fix `childrenOf` (MQ-14).

**Migrations.** Partial `UNIQUE (entity_id) WHERE is_primary` on `entity_aliases`/`entity_locations`/`entity_temporal_ranges`
(after a dedup audit); functional GiST on `COALESCE(territory_geom, geom)`; index on `entities.display_priority`. SRID
enforcement is bundled here only if MVT is later pursued — otherwise documented as a precondition.

**Frontend (`dashboard.tsx` + `historical-map-viewer.tsx`).** Compute bbox from `map.getBounds()`, zoom from
`map.getZoom()`, debounce, pass `AbortSignal`; keep the viewer mounted across empty/error years; fix the feature-contract
type; remove the per-keystroke teardown.

**Caching.** `Cache-Control` + `ETag` from `max(geometry_periods.updated_at)` (or a data-version counter) on the map responses.

## 5. Data flow

One SQL statement per map request (viewport-bounded, deduped, simplified), streamed via `cursor()` + `StreamedResponse`
with cache headers. One statement per map click. List endpoint filters become index-driven.

## 6. Error handling

- Require `year`/range on `/entities/map` → 422 if absent (replaces the silent default).
- Antimeridian/out-of-range longitudes normalized server-side rather than 422.
- `childrenOf`/`children` either implemented or removed so `?parent_id`/`include_children` no longer 500.

## 7. Testing

- Feature tests: confidence filter returns the *most* confident; range request without `year` works; `group` filters;
  `DISTINCT ON` yields one feature per entity; NULLS-LAST ordering; antimeridian viewport returns both sides;
  `?parent_id` no longer 500s.
- `EXPLAIN` assertions (or query-count tests) that the bbox + temporal predicates hit the GiST indexes.
- Frontend tests: debounced single fetch on rapid year change; in-flight abort; viewer stays mounted on an empty year;
  feature-shape contract test.

## 8. Sequencing (feeds the plan)

1. Correctness fixes in the two map actions (confidence, temporal override, group, NULLS-LAST, dedup) — make the endpoint correct.
2. Indexes migration (partial `UNIQUE`, functional GiST, `display_priority`) + temporal predicate rewrite.
3. Zoom simplification + property trim + `COALESCE` filter/serialize + antimeridian.
4. Frontend repoint (bbox/zoom/debounce/abort/mount) + contract type.
5. `ResolveOhmFeatureAction` single-statement rewrite.
6. `EntityBuilder` EXISTS/LATERAL rewrite + `childrenOf` resolution.
7. HTTP caching.
8. (Deferred) MVT tiles + SRID enforcement — separate future spec.

## 9. Risks

- **Behavior parity** of the rewritten query — guard with the existing `MapEntitiesYearFilteringTest` /
  `GeometryPeriodPrecedenceTest` plus new dedup/ordering tests and `EXPLAIN` checks.
- **`UNIQUE` index on dirty data** — run a duplicate-primary audit and resolve before adding the constraint.
- **Frontend test churn** — `dashboard.test.tsx` pins the `/map/year` URL; update it alongside the repoint.
