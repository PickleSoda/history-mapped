# Atlas Vector Tiles (Martin) + OHM Correlation — Design Spec

> **Date:** 2026-10-31
> **Status:** Design (approved) — user chose "Option A + correlation work" on 2026-10-31; the year-representation decision (§3 D2) was delegated to the agent.
> **Area:** `docker/` (new `martin` service, Caddy route) · `api/` (SQL tile function, resolver, importer) · `web/` (tile source, correlation UI) · `pipeline/` (OHM link extraction)
> **Related:** [map-bbox-query-optimization-design](2026-06-12-map-bbox-query-optimization-design.md) (decision D19 "borders from OHM"), [../../architecture/ohm-integration.md](../../architecture/ohm-integration.md), [../plans/2026-10-31-atlas-tiles-ohm-correlation.md](../plans/2026-10-31-atlas-tiles-ohm-correlation.md) (implementation plan).

## 1. Problem

The atlas draws two datasets that never meet.

- **OpenHistoricalMap (OHM) basemap.** The SPA fetches an OHM house style at runtime and rewrites every layer filter on the client for the timeline year (`applyOhmLayerDateFilter`). All borders the user sees are OHM's: by decision D19 the database stores **no polygons** (all 20,677 `geometry_periods` rows are points; `territory_geom` is null everywhere).
- **Our overlay.** One GeoJSON request per viewport layer against `GET /entities/map`, refetched on every pan **and every timeline year**. The payload already carries `ohm_external_id`, but nothing in `web/` reads it.

The only bridge is the click resolver (`web/src/lib/ohm-resolve.ts` → `GET /map/resolve-ohm-feature`), and it is **dead today**: OHM moved its tiler from Tegola to Martin, and the tiles now carry a signed `osm_id` only (negative = relation, positive = node/way); the resolver still looks for `@id` / `osm_type`, finds neither, and never resolves.

Link coverage is thin and untyped in time:

| | Count |
|---|---|
| Entities | 36,983 |
| Entities with an active OHM geo-ref | 3,305 |
| of which OHM **relations** (boundaries) | 1,159 |
| Polities linked to an OHM boundary | 766 of 17,515 |
| Entities with a Wikidata id | 24,517 |
| OHM geo-refs with `temporal_start_year` set | 0 of 3,305 |

What an OHM tile exposes for joining (verified 2026-10-31 by decoding live tiles):

| Tileset / layer | Identity | Dates |
|---|---|---|
| `ohm` / `land_ohm_centroids` (polity label points) | `osm_id` **negative** = relation id | `start_decdate`, `end_decdate`, `start_date`, `end_date` |
| `ohm` / `land_ohm_lines` (boundary lines) | `osm_id` positive = **way** id, `group_id` is not a relation id | same |
| `ohm` / `place_points_centroids` | `osm_id` positive = node (or way centroid), rarely negative | same |
| `ohm_admin` / `boundaries` (polygons, heavy: ~1.3 MB at z5) | `osm_id` **negative** = relation id | same |
| any | `wikidata` key exists but values are absent in practice | — |

So boundary **lines** cannot be joined on the client; label points and polygons can, by relation id.

One more gap shapes expectations: only 62 of the 3,305 OHM-linked entities have a `geometry_periods` row, and the map (REST today, tiles after this work) is driven by `geometry_periods`. The other 3,243 linked entities never reach the map, so the visible correlation starts small and grows with the backfill (which links entities that *do* have periods) and, separately, with giving those entities a period (out of scope here; reported in Task 12).

## 2. Goals / Non-goals

**Goals**
1. **Our overlay becomes vector tiles** served by [Martin](https://martin.maplibre.org/) from the existing PostGIS database, as **all-time** tiles that carry OHM-convention temporal properties. The client filters them with the same function it already uses on OHM layers, so timeline scrubbing needs no network round trip and tiles are cacheable.
2. **A shared identity key** between OHM features and our entities, persisted (`entity_geo_refs`) and **used at render time**: linked OHM labels/polygons are highlighted, hover is synchronised both ways, and clicking an OHM label resolves to our entity again.
3. **Raise link coverage** with a Wikidata-QID backfill and populate `temporal_start_year` / `temporal_end_year` on every OHM geo-ref so the resolver can pick the right entity per year.
4. **One date-filter mechanism** (decimal years, OHM convention) for both sources; one documented year-conversion rule in SQL, PHP and TypeScript.

**Non-goals**
- Running an OHM replica (imposm + Martin over the OHM planet). Deferred; see the assessment of 2026-10-31. Everything here carries over unchanged if that is done later.
- Storing polygons in the database (D19 stands).
- Migrating integer-year storage to decimal dates (see D2).
- Moving the **admin** map (`api/resources/js`) to tiles. It keeps `GET /entities/map`.
- Contributing geometry back to OHM (roadmap OHM phases 4–5).

## 3. Decisions

**D1 — Martin is a sidecar, function source only, no query parameters.** A single PostgreSQL function `tiles.atlas_entities(z, x, y)` builds the MVT. No `year`/`groups` parameters: tiles are independent of UI state, so every pan reuses cached tiles and timeline scrubbing is purely client-side (exactly OHM's own model). Group and type filters are client-side filter expressions on tile properties.

**D2 — Years: keep integer-year storage, derive OHM decimal dates.** OHM cannot change; its tiles use `start_decdate` / `end_decdate` with the convention (verified from live tiles): a year-only date `YYYY` yields `YYYY + 0.00137` as a start and `YYYY + 0.99863` as an end (noon of 1 Jan / 31 Dec), including negative years (`-2999` → `-2998.99863` start). Our data is year-granular (`start_year`, `end_year` integers, inclusive end, BCE negative, no year zero), and a storage migration would touch every consumer (timeline, chronicles, API contracts, pipeline JSONL, campaign tooling, the `int4range` GiST index) to represent precision we do not hold. The comparison surface is what must match OHM, and derived values satisfy it completely. Therefore:

- One rule, implemented three times with parity tests:
  - SQL `tiles.year_to_decdate(year integer, bound text)` → `year + 0.00137` for `'start'`, `year + 0.99863` for `'end'`; NULL in → NULL out.
  - TypeScript `yearToDecdate(year, bound)` in `web/src/lib/ohm-date.ts`.
  - PHP `App\Support\OhmDate::yearToDecdate(int $year, string $bound): float`.
- Tiles emit `start_decdate` / `end_decdate` (visibility window) **and** `start_year` / `end_year` (display values). A NULL `end_year` emits **no** `end_decdate` (unbounded, which the existing filter already treats as "still exists").
- EVENT entities keep the REST "decade-sticky" rule: visibility window is `[start_year − 10, COALESCE(end_year, start_year) + 10]` inclusive years, applied **before** the decdate conversion. Display years stay exact.
- OHM dates → our years (for the geo-ref backfill): `start_year` = the signed year part of `start_date`; `end_year` = the signed year part of `end_date` (inclusive; a feature ending `1800-01-01` is recorded as ending in 1800, a one-year overstatement we accept and document). Missing part → NULL.
- Known caveat (unchanged behaviour): `yearToOhmDate(-753)` emits `-0753`; whether OHM's data uses astronomical year numbering (year 0 = 1 BCE) or not is unverified. We keep sign passthrough everywhere for parity with the existing code; revisit separately if BCE borders look off by one.

**D3 — Identity key = signed OSM id, as OHM's imposm-fed tiles emit it.** Negative = relation, positive = node or way. Tiles emit `ohm_osm_id` (bigint, signed) derived from the entity's active OHM geo-ref (primary first): `relation` → `-id`, `node`/`way` → `+id`. `entity_geo_refs` keeps `provider/external_type/external_id` unchanged. The resolver accepts `osm_id` (signed): negative → relation; positive → node, then way.

**D4 — Density is a rank-based cap per tile and per century, not the REST impact ladder.** The REST thresholds (80/60/40/20 by zoom) do not thin this data: 20,666 of the 20,677 mapped periods score ≥ 62, so a z0 tile would still carry ~5,200 features (~620 KB). Instead `tiles.tile_cap_for_zoom(z)` keeps, within each tile and each 100-year bucket of `start_year`, the top N features ordered by `display_priority DESC NULLS LAST, impact_score DESC NULLS LAST` (curated priority first, then impact): z ≤ 1 → 12, ≤ 3 → 16, ≤ 6 → 24, ≤ 9 → 48, ≤ 12 → 96, else everything. Every era keeps representation at low zoom and tile size is bounded by the cap times the number of active centuries (110 today). Verification statuses as the REST action (pipeline_draft, ohm_draft, auto_validated, needs_review, in_review, human_verified, expert_verified). Geometry: point for OHM-linked entities, else `COALESCE(territory_geom, geom)` simplified by the `ZoomSimplification` ladder (all current rows are points; the branch exists for future app-owned shapes).

**D5 — Correlation rendering (SPA).**
- Our markers: linked entities (`ohm_osm_id` not null) get a distinguishable label colour.
- OHM label points (`land_ohm_centroids`): the `ohm` source gets `promoteId: { land_ohm_centroids: 'osm_id' }` in the normalised style; linked labels receive feature-state `linked` and are painted with the link colour.
- OHM polygons: an `ohm_admin` vector source (`promoteId: 'osm_id'`, minzoom 2) is added to the style with a fill and a line layer that are **hidden** (`visibility: 'none'`) unless a linked entity is hovered or selected; opacity is driven by feature-state `hover` / `selected`. Hidden layers keep MapLibre from requesting the heavy tiles; the implementer must verify this in the network panel and fall back to adding/removing the layers if it does not hold.
- Hover sync both ways through the `hoverId` ephemeral state. That state exists (`useHover`) but nothing writes or reads it today, so this work also wires it: Browse-list rows and our markers write it on mouse enter/leave and render a hovered style from it; OHM label hover writes it through the osm-id → entity-id index built from the loaded entity tiles (`querySourceFeatures`); list/marker hover drives the OHM label + polygon highlight.

**D6 — Backfill = Overpass tags-only extraction (pipeline) → JSONL → Laravel importer.** The pipeline fetches `relation["boundary"="administrative"]` (all, tags only) and `node/way/relation["place"]["wikidata"]` (tags only), plus an optional id list for the existing refs that have neither. The importer (i) fills `temporal_start_year/temporal_end_year`, `temporal_start/temporal_end` and (null or empty) `external_tags` on existing OHM refs, active or not, and (ii) creates refs by **exact** `entities.wikidata_id` match. Rules that the data forces: OHM dates with start after end (11 such pairs among today's linked refs) store no years, only the raw strings; a record whose id already has a ref on the entity, even an inactive one, is skipped (the unique index covers inactive rows, and an editor's deactivation must stand); when several OHM features share one QID the primary is chosen deterministically (relation before way before node, then best overlap with the entity's temporal range, then latest end date) and the rest become `candidate`; a record is `primary` only when the entity has no active primary geo-ref **of any provider**, because `CreateEntityGeoRefAction` would otherwise deactivate it; `retrieval_method = overpass`.

**D7 — Feature flag.** `VITE_MAP_TILES_URL` unset → the current REST GeoJSON path, unchanged. Set (e.g. `http://localhost:3000/tiles`) → tile path. Both coexist for one release; the REST viewport query is disabled in the SPA when tiles are on.

**D8 — Caching.** The function returns `(mvt bytea, key text)` with `key = md5(mvt)` so Martin serves an ETag. Caddy adds `Cache-Control: public, max-age=300` on `/tiles/*`. The service worker caches `/tiles/atlas_entities/` with `StaleWhileRevalidate` (1 day, 2000 entries).

**D9 — Deployment.** Dev: compose service `martin` (image `ghcr.io/maplibre/martin:1.16.1`, config `docker/martin/config.yaml` with `route_prefix: /tiles` — `base_path` only rewrites TileJSON URLs and leaves the routes unprefixed, verified on 1.16.1 — published on `FORWARD_MARTIN_PORT`, default 3000; the connection string comes from `MARTIN_DATABASE_URL`, a name chosen to avoid Martin's deprecation warning on `DATABASE_URL`). Prod: the same service in `docker-compose.prod.yml`, not published; Caddy `handle /tiles/*` on `APP_DOMAIN` → `martin:3000`. Martin connects with the app's `DB_*` credentials (a read-only role is a documented follow-up).

## 4. Tile contract (summary; full contract in `docs/schemas/atlas-tiles.md`)

- TileJSON: `{TILES}/atlas_entities` (its `vector_layers` come from a JSON comment on the SQL function) · tiles: `{TILES}/atlas_entities/{z}/{x}/{y}` · source-layer: `entities` · zoom 0–14 · feature id (`feature.id`, **not** a property): `fid`, a stable 52-bit hash of `geometry_period_id`.
- One feature per **geometry period** (all periods, all time). Properties:

| Property | Type | Notes |
|---|---|---|
| `id` | string (uuid) | entity id |
| `name` | string | primary alias, else entity name |
| `entity_type` | string | enum value |
| `entity_group` | string | UPPERCASE enum value |
| `impact_score` | number or absent | |
| `display_priority` | number or absent | |
| `start_year`, `end_year` | integer or absent | display values |
| `start_decdate`, `end_decdate` | number or absent | visibility window (D2) |
| `entity_color` | string or absent | `attributes->>'entity_color'` |
| `ohm_osm_id` | integer or absent | signed (D3) |

## 5. Components and data flow

```
Postgres (existing)                      Martin (new sidecar)             SPA (web/)
geometry_periods ─┐                      GET /tiles/atlas_entities/z/x/y  vector source "entities"
entities          ├─ tiles.atlas_entity_features (view)                   ├─ fill/line/symbol layers (existing defs)
entity_aliases    │        │                                              ├─ applyOhmLayerDateFilter(sources: ohm + entities)
entity_geo_refs ──┘        └─ tiles.atlas_entities(z,x,y) → (mvt, etag)   ├─ linked-state sync → ohm label + ohm_admin polygon
                                                                          └─ click: local tile lookup, else /map/resolve-ohm-feature?osm_id=
pipeline/ohm_links  ── Overpass (tags only) ── JSONL ── artisan pipeline:import-ohm-links ── entity_geo_refs (years, tags, new QID links)
```

## 6. Testing strategy

- **SQL** (PHPUnit, test DB): view rows (decdate rule, EVENT padding, signed `ohm_osm_id`, alias precedence, status filter); the MVT function (non-empty tile containing the seeded name; rank-based per-century cap; curated priority outranks impact; ETag stable; TileJSON comment).
- **PHP** (PHPUnit): `OhmDate` unit tests (parity table with SQL/TS); importer (updates years/tags, creates primary vs candidate, dry-run writes nothing, QID duplicates reported); resolver `osm_id` (negative → relation, positive → node then way).
- **Web** (Vitest): `yearToDecdate` parity table; date filter applied to `entities` layers only when requested; resolver identity extraction from signed `osm_id`; highlight helpers (pure functions over fake maps).
- **Pipeline** (pytest, fixtures, no network): Overpass element → record mapping; id batching; JSONL writer.
- **Manual**: Martin catalog + a z0 tile from the dev stack; SPA with `VITE_MAP_TILES_URL` set: scrub the timeline with no `/entities/map` requests; hover/select a linked polity and see the OHM label and polygon highlight; click an OHM polity label and land on the entity.

## 7. Risks

- **MapLibre may request tiles for hidden layers' sources.** Verify; fallback in D5.
- **`ohm_admin` tile weight** (~1.3 MB at z5): only loaded while a linked entity is hovered/selected, minzoom 2.
- **Peer branch overlap.** Another session is editing `MapCanvas.tsx` (battle-map overlay) and `api/routes/api.php` in the main checkout. This work lives in a worktree and will be rebased; keep `MapCanvas.tsx` edits surgical and put new logic in new modules.
- **Overpass size/timeouts.** Tags-only queries, 1800 s timeout, resumable artifacts under `output/ohm_links/<run_id>/`.
- **Shared test database** with the peer session: transient failures on concurrent runs; re-run.
- **Visible correlation is small at first** (62 linked features in the tiles before the backfill; see §1). The backfill raises it; the 3,243 linked-but-unmapped entities are a separate data decision.
- **z0 tile cost**: ~1 s and ~620 KB with the REST ladder; the rank cap (D4) is there to keep it a few hundred KB and well under that. Martin's in-memory cache and the ETag absorb repeats.
- **Pre-existing failing test**: `pipeline/tests/test_ohm_borders_fetcher.py::test_assemble_geometry_preserves_contained_outlines_without_extra_deduplication` fails on the base commit; not in scope.
