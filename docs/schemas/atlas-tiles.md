# Atlas vector tiles

> **Audience:** developers, GIS users · **Last reviewed:** 2026-11-18 · **Overview:**
> [Maps, tiles and OHM](../architecture/ohm-integration.md)

All-time vector tiles of our entity overlay, served from PostGIS by [Martin](https://martin.maplibre.org/) or by the app
itself (`TILES_DRIVER`, see Operations). The public SPA (`web/`) reads them when `VITE_MAP_TILES_URL` is set; the admin app keeps the REST `GET /api/v1/entities/map`. Design:
[spec 2026-10-31](../archive/superpowers-specs/2026-10-31-atlas-tiles-ohm-correlation-design.md) (decisions D1–D9).

Code: `tiles` schema in `api/database/migrations/2026_10_31_000001_create_tiles_schema.php` (helpers + view
`tiles.atlas_entity_features`), `2026_10_31_000002_create_atlas_entities_tile_function.php` (`tiles.atlas_entities(z, x, y)`) and
`2026_11_18_000001_tiles_importance_gate_and_feature_table.php` (the feature table, importance gate and current function body);
refresh command `App\Console\Commands\RefreshTilesCommand`; Martin config `docker/martin/config.yaml`; app driver `api/routes/tiles.php` + `App\Services\Tiles\TileServer` (`config/tiles.php`);
client `web/src/lib/map-tiles.ts`. Tests: `api/tests/Feature/Tiles/`.

## Endpoints

`{TILES}` is the tile root: in dev `http://localhost:8000/tiles` (the app) or `http://localhost:3000/tiles` (Martin); in prod
`https://<APP_DOMAIN>/tiles`, where Caddy proxies to whichever driver `TILES_DRIVER` names. Both drivers answer these three paths
the same way.

| Path | Returns |
|---|---|
| `{TILES}/catalog` | The source list; `tiles.atlas_entities` appears as `atlas_entities` |
| `{TILES}/atlas_entities` | TileJSON 3.0.0. `vector_layers` comes from the JSON comment on the SQL function; `tiles` is built from the request host |
| `{TILES}/atlas_entities/{z}/{x}/{y}` | `application/x-protobuf` MVT, zoom 0–14 (the SPA overzooms past 14). Gzip when the client accepts it |

- Martin answers only under `/tiles` (`route_prefix`); `/catalog` is 404.
- The app driver's routes carry no middleware group (no session, CSRF or API throttle) and answer with
  `Access-Control-Allow-Origin: *`, as Martin does. An unknown source or a non-numeric coordinate is 404.
- An empty tile is `204 No Content`. Coordinates outside the zoom's grid also return an empty tile, not a 500.
- The SPA does not read the TileJSON. It builds `{VITE_MAP_TILES_URL}/atlas_entities/{z}/{x}/{y}` itself (`entityTileSource()`).
- Size on the dev DB, 2026-10-31: z0 `0/0/0` is 111,624 bytes (66,980 gzip).

## Features

- One layer, **`entities`** (the source-layer name).
- One feature per **geometry period**, for all periods of all time. An entity with several periods appears once per period, with
  the same `id` and a different feature id.
- Feature id (`feature.id`, **not** a property) is `fid`, a stable 52-bit hash of `geometry_period_id`
  (`('x' || left(md5(geometry_period_id::text), 13))::bit(52)::bigint`). It is a safe JavaScript integer.
- Geometry is the period's point when the feature is linked to OHM (`ohm_osm_id` present). Otherwise it is
  `COALESCE(territory_geom, geom)`, with non-point shapes simplified per zoom (`tiles.simplify_tolerance`: 0.5° at z ≤ 3, 0.1 at ≤ 6,
  0.02 at ≤ 9, 0.005 at ≤ 12, none above). All current rows are points (D19: no stored polygons).
- Extent 4096, buffer 64, clipped.
- Entities are included when `verification_status` is one of `pipeline_draft`, `ohm_draft`, `auto_validated`, `needs_review`,
  `in_review`, `human_verified` or `expert_verified`. This is the same list as the REST action.

### Properties

MVT drops NULL values, so "absent" means the column was NULL.

| Property | MVT type | Notes |
|---|---|---|
| `id` | string | entity uuid |
| `name` | string | primary alias (latest updated), else `entities.name` |
| `entity_type` | string | `EntityType` value (lowercase) |
| `entity_group` | string | `EntityGroup` value (UPPERCASE) |
| `impact_score` | integer, or absent | |
| `display_priority` | integer, or absent | curated priority |
| `start_year` | integer | display value; always present (`geometry_periods.start_year` is NOT NULL) |
| `end_year` | integer, or absent | display value; absent = ongoing |
| `start_decdate` | double | start of the visibility window (decimal year, see below); always present |
| `end_decdate` | double, or absent | end of the visibility window; absent = open-ended |
| `entity_color` | string, or absent | `entities.attributes->>'entity_color'` |
| `ohm_osm_id` | integer (signed), or absent | OHM feature this entity links to, see below |
| `has_map_story` | boolean | entity has a map story (a `map_stories` row); always present. Same as REST `has_map_story` (migration `2026_10_31_000003_add_has_map_story_to_tiles.php`) |

The TileJSON advertises the same thirteen fields (`String` / `Number` / `Boolean`).

## Visibility window: the decimal-date rule

OHM tiles carry `start_decdate` / `end_decdate`. For a year-only date, OHM writes noon on 1 January as the start and noon on
31 December as the end (verified on live tiles). We store integer years (inclusive end, BCE negative) and derive the same values:

- start: `year + 0.00137`
- end: `year + 0.99863`

So `1900` gives `1900.00137` as a start, and `-2999` gives `-2998.99863`.

The rule is implemented three times, with parity tests on the same table:

| Where | Implementation |
|---|---|
| SQL | `tiles.year_to_decdate(year integer, bound text)` (`'start'` / `'end'`; NULL in → NULL out) |
| PHP | `App\Support\OhmDate::yearToDecdate(int $year, string $bound): float` |
| TypeScript | `yearToDecdate(year, bound)` in `web/src/lib/ohm-date.ts` |

**EVENT entities** keep the REST "decade-sticky" rule. The window is `[start_year − 10, COALESCE(end_year, start_year) + 10]` in
inclusive years, applied before the conversion. `start_year` / `end_year` stay exact. For example, 1066 gives
`1056.00137 … 1076.99863`.

**Client filter** (`entityLayerFilter` in `web/src/lib/map-tiles.ts`). The SPA computes the timeline position's decimal range
with `ohmDateRange`, reading the year as written: these decimal dates use our numbering. (The OHM basemap's filter first moves
a BCE year to OHM's astronomical number, where year 0 is 1 BCE.) It keeps features where `start_decdate <= range.end` and
(`end_decdate` absent or `end_decdate >= range.start`). It then applies the group subset as
`['in', ['get', 'entity_group'], ['literal', [...UPPERCASE]]]`. Scrubbing the timeline fetches no tiles. The sidebar
list (`GET /api/v1/entities?exists_at=…`) and the ambient stories still refetch for the new year.

## Density: importance gate, then a cap per tile and per century

Two rules, applied in this order.

**1. Importance gate.** Each feature has a `min_zoom`, from `tiles.feature_min_zoom(entity_group, entity_type, importance)`, where
importance is `GREATEST(display_priority, impact_score)` (a curated priority can raise a feature, never bury it). A tile at zoom z
holds only features with `min_zoom <= z`. Places wait for close zooms whatever their score: city scores do not tell a capital
from a hamlet.

| Feature | Importance | First zoom |
|---|---|---|
| City (`city`) | ≥ 80 | 7 |
| City | below 80 | 9 |
| Other place (group `PLACE`: monuments, schools, mines…) | ≥ 70 | 9 |
| Other place | below 70 | 11 |
| Everything else (events, polities, culture…) | ≥ 90 | 0 |
| | 80–89 | 3 |
| | 70–79 | 5 |
| | 60–69 | 7 |
| | below 60 | 9 |

**2. Cap per century.** Within one tile, the features that pass are grouped into 100-year buckets of `start_year`
(`floor(start_year / 100.0)`). Each bucket keeps its top N, ordered by `display_priority DESC NULLS LAST`, then
`impact_score DESC NULLS LAST`, then `geometry_period_id`. N comes from `tiles.tile_cap_for_zoom(z)`:

| Zoom | ≤ 1 | ≤ 3 | ≤ 6 | ≤ 9 | ≤ 12 | ≥ 13 |
|---|---|---|---|---|---|---|
| N | 8 | 12 | 16 | 32 | 64 | no cap |

Every era with an important enough feature keeps some at low zoom. The cost of this rule: a long-lived entity competes only in the
century its period starts in. The REST impact ladder does not apply to tiles (D4).

On the 641k-entity database (57k periods), z0 went from 121 KB and 0.43 s to 41 KB and 22 ms; a world tile holds about 300
features across all eras, with no city before z7 and no other place before z9.

## The feature table: `tiles.atlas_features`

Tiles are cut from `tiles.atlas_features`, a materialized copy of the view plus `century` and `min_zoom` (about 15 MB). Reading
the view per tile joined the 1 GB `entities` table on every request; the z0 tile took 16 s cold on the 2 GB droplet.

| Piece | Role |
|---|---|
| `tiles.change_seq` | Bumped by statement-level triggers (`tiles_note_change`) on `geometry_periods`, `entities`, `entity_aliases`, `entity_geo_refs` and `map_stories` |
| `php artisan tiles:refresh` | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (tiles keep serving), but only when `change_seq` moved since the last refresh (remembered in the cache store). `--force` always refreshes |
| Scheduler | Runs `tiles:refresh` every five minutes |
| Content load | A data-only `pg_dump` carries no materialized-view rows and the load disables triggers, so the loader runs `tiles:refresh --force` |
| Tests | Refresh the table before reading a tile (`REFRESH MATERIALIZED VIEW tiles.atlas_features`) |

## Link to OHM: `ohm_osm_id`

The id is signed the way OHM's tiles sign `osm_id`: **negative = relation, positive = node or way** (D3). It comes from the
entity's top active OHM geo-ref: `match_role = primary` first, then the latest `updated_at`.

- `relation/1880` gives `-1880`; `node/42` and `way/42` give `42`.
- It is absent when that ref's type is not relation, node or way, or its `external_id` is not a positive integer of at most
  18 digits (`tiles.signed_osm_id`, parity with `OhmDate::signedOsmId`).
- **Linked means "has a resolvable signed id".** A feature without `ohm_osm_id` is unlinked everywhere in tile mode: it keeps
  its own geometry instead of the point, uses the default label colour, and gets no OHM highlight. REST serves the point for
  any entity with an active OHM ref, even one without a usable id; tiles do not.
- In OHM's own tiles the same number appears as `osm_id` on `ohm` / `land_ohm_centroids` and on `ohm_admin` / `boundaries`. The
  SPA promotes it to the feature id there to drive highlights. The reverse lookup is
  `GET /api/v1/map/resolve-ohm-feature?provider=ohm&osm_id=<signed>&target_year=<year>`. See
  [Maps, tiles and OHM § Linking our entities to OHM](../architecture/ohm-integration.md#linking-our-entities-to-ohm).

## Caching

| Layer | Behaviour |
|---|---|
| ETag | The function returns `(mvt, key)` with `key = md5(mvt)`; both drivers send it as `ETag` and answer a matching `If-None-Match` with 304 |
| Martin | In-memory tile cache, `cache.size_mb: 128` and `cache.expiry: 5m`, so data edits and backfills show up without a restart |
| App driver | Rendered tiles in the cache store (`CACHE_STORE`, Redis in prod) for `TILES_CACHE_TTL` seconds (default 300; 0 = off) |
| Caddy (prod) | `Cache-Control: public, max-age=300` and gzip/zstd on `/tiles/*`, whichever the driver. Dev has no Caddy: Martin sends no `Cache-Control`, the app sends `max-age=300, public` |
| Service worker | `StaleWhileRevalidate` on `/tiles/atlas_entities/`, cache `atlas-tiles`, 2000 entries, 1 day (`web/vite.config.ts`) |

A data change reaches a returning browser within about 15 minutes (the five-minute `tiles:refresh`, Martin expiry and HTTP
max-age). The service worker serves one stale copy first, then revalidates in the background.

## Feature flag

`VITE_MAP_TILES_URL` (D7) is baked into the SPA bundle at build time.

- Unset or empty: the REST GeoJSON path (`GET /api/v1/entities/map` per viewport and year) is unchanged.
- Set: the `entities` source becomes the tile source and the viewport query is disabled. Trailing slashes are stripped.

Dev: `web/.env.example` (commented out). Prod: the GitHub repository variable `VITE_MAP_TILES_URL`, baked into the `web` image by CI (see the deployment runbook).

## Operations

- **Driver:** `TILES_DRIVER=martin|app` in `docker/.env.prod` (default `martin`). Caddy imports the matching upstream snippet
  (`docker/Caddyfile`), and `docker/compose-prod.sh` enables the `martin` compose profile only for `martin`, so the sidecar runs
  only when it is the driver. Switching needs no SPA rebuild: the URLs are the same. The app driver is one container fewer, but
  its tile requests share Octane's PHP workers (`OCTANE_WORKERS`, 4 in prod) with the API; Martin has its own pool and cache.
- **Martin version:** `ghcr.io/maplibre/martin:1.16.1`, pinned in both compose files.
- **Connection:** `MARTIN_DATABASE_URL`, built from `POSTGRES_*` in dev and `DB_*` in prod (keep `DB_PASSWORD` URL-safe). Martin
  uses the app's credentials; a read-only role is a follow-up.
- **Martin only publishes functions in schema `tiles`, and finds them at startup.** Restart it after every migration that
  touches `tiles`: new functions and changed TileJSON comments are only picked up at startup.
  - Dev: `docker compose -f docker/docker-compose.yml restart martin`.
  - Prod: the CI deploy recreates `martin` and `caddy` after `migrate`; see
    [deployment-runbook.md §3](../implementation-docs/deployment-runbook.md#3-the-droplet-self-hosted-compose).
- **Parity with REST:** the view mirrors `App\Actions\Entity\MapEntitiesAction`. A property added to the REST projection must also
  be added to the view, the function's SELECT list and its JSON comment (new migration), and to this table.
