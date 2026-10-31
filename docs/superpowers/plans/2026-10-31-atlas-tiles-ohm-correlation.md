# Atlas Vector Tiles (Martin) + OHM Correlation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve our entity overlay as all-time vector tiles from Martin, link those features to OpenHistoricalMap (OHM) basemap features by signed OSM id, highlight and resolve the links in the atlas SPA, and backfill the links and their temporal ranges from OHM via Wikidata ids.

**Architecture:** A `tiles` schema in the existing PostGIS database holds a feature view and one MVT function that Martin (sidecar container) publishes; the SPA switches its `entities` source to that tile endpoint behind `VITE_MAP_TILES_URL`, filters features client-side with OHM's decimal-date convention, and uses `ohm_osm_id` to drive feature-state highlights on OHM labels/polygons and the click resolver. A pipeline command extracts OHM tags via Overpass to JSONL; an artisan importer fills `entity_geo_refs`.

**Tech Stack:** PostgreSQL 16 + PostGIS 3.5 (`ST_AsMVT`), Martin 1.16.1, Laravel 13 / PHPUnit, React 19 + MapLibre GL v5 + TanStack Query / Vitest, Python 3 (click, requests) / pytest, Docker Compose, Caddy.

**Spec:** [../specs/2026-10-31-atlas-tiles-ohm-correlation-design.md](../specs/2026-10-31-atlas-tiles-ohm-correlation-design.md) — read it first; decisions are referenced as D1…D9.

---

## Working rules for this plan (read before any task)

**Where to work.** This branch lives in a git worktree, not the main checkout, because another session is editing the main checkout concurrently:

```
WT=/home/pickle/code/history-mapped/.claude/worktrees/martin-tiles     # branch feat/martin-tiles-ohm-correlation
```

Run every command from `$WT`. Never `cd` into `/home/pickle/code/history-mapped` itself, never switch branches, never `git stash`, never `git push`. Commit with explicit paths (`git add <files>`; never `git add -A`). Conventional messages (`feat(tiles): …`, `fix(web): …`), ending with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

**The dev stack's containers mount the main checkout, not the worktree.** Run tests in one-off containers that mount `$WT` (verified working on 2026-10-31):

```bash
# PHP (PHPUnit / artisan / pint) — uses the shared test DB `history-mapped_test`
PHP="docker run --rm --network history-mapped_default -v $WT/api:/var/www/html -v history-mapped_api_vendor:/var/www/html/vendor -w /var/www/html history-mapped-app"
$PHP php artisan test --filter=SomeTest
$PHP vendor/bin/pint --test app/Support/OhmDate.php
$PHP php artisan migrate            # applies to the SHARED dev DB (additive only; fine)

# Web (vitest / eslint / tsc)
WEB="docker run --rm --network history-mapped_default -v $WT:/workspace -v history-mapped_root_node_modules:/workspace/node_modules -v history-mapped_web_node_modules:/workspace/web/node_modules -v history-mapped_pnpm_store:/pnpm/store -w /workspace history-mapped-web"
$WEB pnpm --filter @history-mapped/web exec vitest run src/lib/ohm-date.test.ts
$WEB pnpm --filter @history-mapped/web lint
$WEB pnpm --filter @history-mapped/web types:check

# Pipeline (host, uv)
cd $WT && uv run --with pytest pytest pipeline/tests/test_ohm_links_records.py -q

# Martin one-off against the dev DB (image is pulled locally)
docker run --rm --name martin-wt --network history-mapped_default -p 3011:3000 \
  -v $WT/docker/martin/config.yaml:/config/martin.yaml:ro \
  -e MARTIN_DATABASE_URL=postgresql://history-mapped:secret@db:5432/history-mapped \
  ghcr.io/maplibre/martin:1.16.1 --config /config/martin.yaml
```

**Manual verification stack (Tasks 9–11).** The main stack's API (`:8000`) does not have this branch's code and its CORS only allows `http://localhost:5173`, so run the worktree's own API and SPA (after `$PHP php artisan migrate`):

```bash
# API from the worktree on :8011 (CORS/Sanctum opened for the :5175 SPA)
docker run --rm --name api-wt --network history-mapped_default -p 8011:8011 \
  -v $WT/api:/var/www/html -v history-mapped_api_vendor:/var/www/html/vendor -w /var/www/html \
  -e APP_URL=http://localhost:8011 -e FRONTEND_URL=http://localhost:5175 -e SANCTUM_STATEFUL_DOMAINS=localhost:5175 \
  history-mapped-app php artisan serve --host 0.0.0.0 --port 8011
# Martin from the worktree config on :3011 (see above), then the SPA on :5175
docker run --rm --name web-wt --network history-mapped_default -p 5175:5173 \
  -v $WT:/workspace -v history-mapped_root_node_modules:/workspace/node_modules -v history-mapped_web_node_modules:/workspace/web/node_modules -v history-mapped_pnpm_store:/pnpm/store -w /workspace \
  -e VITE_API_URL=http://localhost:8011 -e VITE_MAP_TILES_URL=http://localhost:3011/tiles \
  history-mapped-web pnpm --filter @history-mapped/web dev --host
```

Stop all three containers when done (`docker rm -f api-wt web-wt martin-wt`).

**Docker quirk.** `~/.docker/config.json` names a credential helper that is not installed, so pulling a *new* image fails with `docker-credential-desktop: executable file not found`. Work around it with an empty config dir: `DOCKER_CONFIG=$(mktemp -d) docker pull …`. Images already present run fine without it.

**Pre-existing failure (ignore):** `pipeline/tests/test_ohm_borders_fetcher.py::test_assemble_geometry_preserves_contained_outlines_without_extra_deduplication` fails on the base commit.

**GitNexus.** `CLAUDE.md` asks for `impact` analysis before editing a symbol. If the GitNexus MCP tools are not available in your session, grep for callers of every function you modify and list them in your report instead.

---

## File structure

| File | Change |
|------|--------|
| `api/database/migrations/2026_10_31_000001_create_tiles_schema.php` | Create: schema `tiles`, helper functions, view `tiles.atlas_entity_features` |
| `api/database/migrations/2026_10_31_000002_create_atlas_entities_tile_function.php` | Create: `tiles.atlas_entities(z,x,y)` MVT function |
| `api/tests/Feature/Tiles/AtlasEntityFeaturesViewTest.php`, `AtlasEntitiesTileFunctionTest.php` | Create: SQL behaviour tests |
| `docker/martin/config.yaml` | Create: Martin config (D9) |
| `docker/docker-compose.yml`, `docker/docker-compose.prod.yml`, `docker/Caddyfile`, `.env.example`, `docker/.env.prod.example` | Modify: `martin` service, `/tiles` route, env vars |
| `api/app/Support/OhmDate.php` + `api/tests/Unit/Support/OhmDateTest.php` | Create: year/decdate/signed-id rules (D2, D3) |
| `api/app/Http/Api/V1/Requests/ResolveOhmFeatureRequest.php`, `api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php` | Modify: accept signed `osm_id` |
| `api/tests/Feature/Api/ResolveOhmFeatureSignedIdTest.php` | Create |
| `pipeline/ohm_links/{__init__,__main__,fetcher,records,writer}.py` + `pipeline/tests/test_ohm_links_*.py` | Create: Overpass tags-only extraction (D6) |
| `pipeline/__main__.py` | Modify: register `ohm-links` group |
| `api/app/Console/Commands/ExportOhmRefIdsCommand.php`, `ImportOhmLinksCommand.php`, `api/app/Actions/EntityGeoRef/ImportOhmLinksAction.php` | Create: importer (D6) |
| `api/tests/Feature/Console/ImportOhmLinksTest.php`, `ExportOhmRefIdsTest.php` | Create |
| `web/src/lib/ohm-date.ts`, `web/src/lib/ohm-layer-date-filter.ts` (+ tests) | Modify: `yearToDecdate`, exported `ohmDateRange` |
| `web/src/lib/map-tiles.ts` (+ test) | Create: tile source spec, entity-layer filter builder, flag |
| `web/src/components/map/MapCanvas.tsx`, `web/src/hooks/useEntitiesInView.ts`, `web/src/lib/schemas/map.ts`, `web/vite.config.ts`, `web/.env.example` | Modify: tile mode (D7, D8) |
| `web/src/lib/ohm-resolve.ts` (+ test) | Modify: signed `osm_id`, local tile lookup |
| `web/src/lib/map-config.ts`, `web/src/lib/ohm-highlight.ts` (+ test), `web/src/components/atlas/BrowseTab.tsx` | Modify/Create: promoteId, `ohm_admin` source, highlight state, hover plumbing (D5) |
| `docs/schemas/atlas-tiles.md`, `docs/schemas/README.md`, `docs/architecture/ohm-integration.md`, `docs/architecture/frontend-app.md`, `docs/implementation-docs/setup.md`, `docs/implementation-docs/deployment-runbook.md`, `docs/plans/STATUS.md`, `CLAUDE.md` | Docs |

**Dependency order.** Tasks 1 → 2 → 3 are sequential. Tasks 4, 6 and 8 are independent of each other and of 1–3. Task 5 and 7 need 4. Task 9 needs 2, 3 and 8. Task 10 needs 5 and 9. Task 11 needs 9. Task 12 needs 6 and 7 (and a running dev DB). Task 13 is last.

---

## Phase 1 — Database and tile server

### Task 1: `tiles` schema, year conversion, and the feature view

**Files:**
- Create: `api/database/migrations/2026_10_31_000001_create_tiles_schema.php`
- Test: `api/tests/Feature/Tiles/AtlasEntityFeaturesViewTest.php`

Context: everything Martin serves comes from one view. It mirrors the REST projection in `api/app/Actions/Entity/MapEntitiesAction.php` (alias precedence, OHM ref subquery, status list, EVENT padding, point-for-OHM-linked rule) but emits **all periods, all time** plus OHM-convention decimal dates (D2) and a signed OSM id (D3). Look at `MapEntitiesAction.php` and `api/tests/Feature/Api/MapEntitiesOhmRefTest.php` for the seeding style (raw `INSERT` into `geometry_periods` / `entity_geo_refs`, `Entity::factory()->verified()`).

- [ ] **Step 1: Write the failing test** `AtlasEntityFeaturesViewTest` (extends `Tests\TestCase` and declares `use RefreshDatabase;` like every DB feature test — `TestCase` itself does not refresh) with these cases, each seeding through raw SQL like `MapEntitiesOhmRefTest`:
  1. `test_decdate_follows_ohm_convention`: a period 1900–1950 yields `start_decdate = 1900.00137`, `end_decdate = 1950.99863`; a period with `end_year NULL` yields `end_decdate NULL`; a period −2999 … −2799 yields `-2998.99863` / `-2798.00137`.
  2. `test_event_window_is_padded_ten_years_but_display_years_are_exact`: an `EVENT` entity with start = end = 1066 yields `start_year 1066`, `end_year 1066`, `start_decdate 1056.00137`, `end_decdate 1076.99863`.
  3. `test_ohm_relation_ref_emits_negative_signed_id_and_point_geometry`: entity with an active primary OHM ref `relation/1880` and a period holding both a point and a polygon → `ohm_osm_id = -1880` and `ST_GeometryType(geom) = 'ST_Point'`; a `node/42` ref → `42`; no ref → `NULL`.
  4. `test_primary_alias_wins_over_entity_name` (insert into `entity_aliases` with `is_primary = true`).
  5. `test_rejected_entities_are_excluded` (an entity with `verification_status = 'rejected'` has no row; check the enum value exists in `App\Enums\VerificationStatus`, otherwise use any status outside the allowed list).
  6. `test_fid_is_stable_and_fits_52_bits`: query the row twice; same `fid`; `fid BETWEEN 0 AND 4503599627370495`.

- [ ] **Step 2: Run → FAIL** (`relation "tiles.atlas_entity_features" does not exist`): `$PHP php artisan test --filter=AtlasEntityFeaturesViewTest`

- [ ] **Step 3: Write the migration.** `up()` runs these statements with `DB::unprepared()` (one block is fine; put the SQL in a PHP **nowdoc** `<<<'SQL'` because it contains `$$`); `down()` drops the view, the functions and the schema (`DROP SCHEMA IF EXISTS tiles CASCADE`).

```sql
CREATE SCHEMA IF NOT EXISTS tiles;

-- D2: OHM decimal-date convention for a year-only date.
CREATE OR REPLACE FUNCTION tiles.year_to_decdate(year integer, bound text)
RETURNS double precision LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE bound
    WHEN 'start' THEN year + 0.00137
    WHEN 'end'   THEN year + 0.99863
  END::double precision
$$;

--- D4: per-tile, per-century cap by rank (NULL = keep everything).
CREATE OR REPLACE FUNCTION tiles.tile_cap_for_zoom(z integer)
RETURNS integer LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE WHEN z <= 1 THEN 12 WHEN z <= 3 THEN 16 WHEN z <= 6 THEN 24 WHEN z <= 9 THEN 48 WHEN z <= 12 THEN 96 END
$$;

-- Mirrors App\Services\ZoomSimplification (tolerance only; MVT quantises digits itself).
CREATE OR REPLACE FUNCTION tiles.simplify_tolerance(z integer)
RETURNS double precision LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE WHEN z <= 3 THEN 0.5 WHEN z <= 6 THEN 0.1 WHEN z <= 9 THEN 0.02 WHEN z <= 12 THEN 0.005 ELSE 0.0 END
$$;

-- D3: signed OSM id as OHM's imposm-fed tiles emit it (negative = relation).
CREATE OR REPLACE FUNCTION tiles.signed_osm_id(external_type text, external_id text)
RETURNS bigint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT CASE
    WHEN external_id IS NULL OR external_id !~ '^[0-9]{1,18}$' THEN NULL
    WHEN external_type = 'relation' THEN -(external_id::bigint)
    WHEN external_type IN ('node', 'way') THEN external_id::bigint
  END
$$;

CREATE OR REPLACE VIEW tiles.atlas_entity_features AS
SELECT
  gp.geometry_period_id,
  ('x' || left(md5(gp.geometry_period_id::text), 13))::bit(52)::bigint AS fid,
  e.entity_id::text AS id,
  COALESCE(
    (SELECT a.name FROM entity_aliases a
      WHERE a.entity_id = e.entity_id AND a.is_primary = true
      ORDER BY a.updated_at DESC NULLS LAST, a.created_at DESC NULLS LAST LIMIT 1),
    e.name) AS name,
  e.entity_type::text AS entity_type,
  e.entity_group::text AS entity_group,
  e.impact_score,
  e.display_priority,
  gp.start_year,
  gp.end_year,
  tiles.year_to_decdate(
    CASE WHEN e.entity_group::text = 'EVENT' THEN gp.start_year - 10 ELSE gp.start_year END, 'start') AS start_decdate,
  tiles.year_to_decdate(
    CASE WHEN e.entity_group::text = 'EVENT' THEN COALESCE(gp.end_year, gp.start_year) + 10 ELSE gp.end_year END, 'end') AS end_decdate,
  e.attributes->>'entity_color' AS entity_color,
  ohm.osm_id AS ohm_osm_id,
  COALESCE(gp.territory_geom, gp.geom) AS bbox_geom,   -- matches index gp_map_geom_gist
  CASE WHEN ohm.osm_id IS NOT NULL THEN gp.geom ELSE COALESCE(gp.territory_geom, gp.geom) END AS geom
FROM geometry_periods gp
JOIN entities e ON e.entity_id = gp.entity_id
LEFT JOIN LATERAL (
  SELECT tiles.signed_osm_id(egr.external_type::text, egr.external_id) AS osm_id
  FROM entity_geo_refs egr
  WHERE egr.entity_id = e.entity_id AND egr.provider = 'ohm' AND egr.is_active = true
  ORDER BY (egr.match_role = 'primary') DESC, egr.updated_at DESC NULLS LAST
  LIMIT 1
) ohm ON true
WHERE (gp.geom IS NOT NULL OR gp.territory_geom IS NOT NULL)
  AND e.verification_status IN ('pipeline_draft', 'ohm_draft', 'auto_validated', 'needs_review',
                                'in_review', 'human_verified', 'expert_verified');
```

  Column types (verified 2026-10-31): `impact_score` and `display_priority` are `integer`; `entity_group`, `entity_type`, `verification_status` and `match_role` are Postgres enums, so the `::text` casts above are required and the enum-vs-literal comparisons are valid.

- [ ] **Step 4: Run → PASS.** Also run `$PHP php artisan test --filter=MapEntities` to be sure nothing else broke, and `$PHP vendor/bin/pint --test database/migrations/2026_10_31_000001_create_tiles_schema.php tests/Feature/Tiles`.

- [ ] **Step 5: Confirm the index is usable:** `EXPLAIN SELECT fid FROM tiles.atlas_entity_features WHERE bbox_geom && ST_MakeEnvelope(0,0,10,10,4326)` must mention `gp_map_geom_gist`. If it does not, note it in your report (do not restructure the view on your own).

- [ ] **Step 6: Commit** `feat(tiles): tiles schema with OHM decimal-date rule and entity feature view`

### Task 2: The MVT function `tiles.atlas_entities(z, x, y)`

**Files:**
- Create: `api/database/migrations/2026_10_31_000002_create_atlas_entities_tile_function.php`
- Test: `api/tests/Feature/Tiles/AtlasEntitiesTileFunctionTest.php` (declare `use RefreshDatabase;`)

Context: Martin auto-publishes any function in schema `tiles` with signature `(z integer, x integer, y integer)` returning `TABLE(mvt bytea, key text)`; `key` becomes the ETag (D8). The function's SQL comment is merged into its TileJSON, which is how `vector_layers` gets advertised. Density is D4: **rank-based** per tile per century (the REST impact ladder does not thin this data: 20,666 of 20,677 mapped periods score ≥ 62, so an impact threshold would still emit ~5,200 features / ~620 KB at z0). PostGIS 3.5 is in the `db` image, so `ST_AsMVT(row, name, extent, geom_col, feature_id_col)` is available. The ranking CTE must reference only cheap columns of the view (so the planner drops the alias subquery and the OHM lateral for rows that are not kept) and join the view back by `geometry_period_id` for the kept rows.

- [ ] **Step 1: Write the failing test.** Seed with raw SQL; every seeded entity gets `display_priority = NULL` (the factory randomises it, which would make the rank tests flaky) and a unique name that is not a prefix of another seeded name (`position(… IN mvt)` is a substring test: use `Cap01 Zed`, `Cap02 Zed`, …). Point `ST_Point(10.5, 40.5)` lies in tile z0 `0/0` and z12 `2167/1543` (check in the test with `SELECT ST_Intersects(ST_TileEnvelope(12, 2167, 1543), ST_Transform(ST_SetSRID(ST_Point(10.5, 40.5), 4326), 3857))`). Cases:
  1. `test_tile_contains_seeded_feature_and_name`: `SELECT mvt, key FROM tiles.atlas_entities(0, 0, 0)` returns `length(mvt) > 0` and `position(convert_to('Testland Unique Name', 'UTF8') IN mvt) > 0`.
  2. `test_etag_is_md5_of_tile_and_stable`: `key = md5(mvt)`; two calls return equal keys.
  3. `test_per_century_cap_keeps_top_ranked_at_low_zoom`: seed 13 entities in the same century (start_year 1000–1012) with impacts 70…58 (distinct) and one period each; at z0 (`cap 12`) the lowest-impact name is absent and the other 12 are present; at z12 `2167/1543` all 13 are present.
  4. `test_curated_priority_outranks_impact`: among 13 same-century entities, the one with `display_priority = 10` and impact 1 is present at z0 while the lowest-impact NULL-priority one is absent.
  5. `test_cap_is_per_century`: 12 entities in century 10 and 12 in century 15 → all 24 present at z0.
  6. `test_empty_tile_returns_empty_bytea_not_null`: `SELECT mvt FROM tiles.atlas_entities(14, 0, 0)` returns `''::bytea`.
  7. `test_tilejson_comment_declares_the_entities_layer`: `SELECT obj_description('tiles.atlas_entities(integer,integer,integer)'::regprocedure, 'pg_proc')` parses as JSON whose `vector_layers[0].id = 'entities'`.

- [ ] **Step 2: Run → FAIL**: `$PHP php artisan test --filter=AtlasEntitiesTileFunctionTest`

- [ ] **Step 3: Write the migration** (`DB::unprepared` with a nowdoc; `down()` drops the function):

```sql
CREATE OR REPLACE FUNCTION tiles.atlas_entities(z integer, x integer, y integer)
RETURNS TABLE (mvt bytea, key text)
LANGUAGE plpgsql STABLE STRICT PARALLEL SAFE
SET jit = off   -- the cost estimate triggers ~0.7 s of JIT compilation per call; ~0.1 s without it
AS $$
DECLARE
  env3857 geometry := ST_TileEnvelope(z, x, y);
  env4326 geometry := ST_Transform(ST_TileEnvelope(z, x, y), 4326);
  cap     integer  := tiles.tile_cap_for_zoom(z);
  tol     double precision := tiles.simplify_tolerance(z);
  tile    bytea;
BEGIN
  SELECT ST_AsMVT(t, 'entities', 4096, 'geom', 'fid') INTO tile
  FROM (
    WITH ranked AS (
      -- Only cheap columns here: the planner then skips the alias subquery for
      -- rows that are not kept (the OHM lateral still runs per row, ~2 µs each).
      SELECT f.geometry_period_id,
             row_number() OVER (
               PARTITION BY floor(f.start_year / 100.0)
               ORDER BY f.display_priority DESC NULLS LAST, f.impact_score DESC NULLS LAST, f.geometry_period_id
             ) AS rn
      FROM tiles.atlas_entity_features f
      WHERE f.bbox_geom && env4326
    ),
    kept AS (
      SELECT geometry_period_id FROM ranked WHERE cap IS NULL OR rn <= cap
    )
    SELECT
      ST_AsMVTGeom(
        ST_Transform(
          CASE WHEN tol > 0 AND ST_Dimension(f.geom) > 0
               THEN ST_SimplifyPreserveTopology(f.geom, tol) ELSE f.geom END,
          3857),
        env3857, 4096, 64, true) AS geom,
      f.fid,
      f.id,
      f.name,
      f.entity_type,
      f.entity_group,
      f.impact_score,
      f.display_priority,
      f.start_year,
      f.end_year,
      f.start_decdate,
      f.end_decdate,
      f.entity_color,
      f.ohm_osm_id
    FROM kept k
    JOIN tiles.atlas_entity_features f ON f.geometry_period_id = k.geometry_period_id
  ) AS t
  WHERE t.geom IS NOT NULL;

  mvt := COALESCE(tile, ''::bytea);
  key := md5(mvt);
  RETURN NEXT;
END
$$;

COMMENT ON FUNCTION tiles.atlas_entities(integer, integer, integer) IS
'{"vector_layers":[{"id":"entities","fields":{"id":"String","name":"String","entity_type":"String","entity_group":"String","impact_score":"Number","display_priority":"Number","start_year":"Number","end_year":"Number","start_decdate":"Number","end_decdate":"Number","entity_color":"String","ohm_osm_id":"Number"}}]}';
```

- [ ] **Step 4: Run → PASS**; Pint on the new files.

- [ ] **Step 5: Smoke against real data** (shared dev DB; additive): `$PHP php artisan migrate`, then with `docker compose -f /home/pickle/code/history-mapped/docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped` run `\timing` and `SELECT length(mvt), key FROM tiles.atlas_entities(0,0,0);`, `… (2,2,1);`, `… (5,17,11);`. Also `EXPLAIN (ANALYZE, SUMMARY OFF) SELECT * FROM tiles.atlas_entities(0,0,0)` is opaque for plpgsql, so instead run `EXPLAIN ANALYZE` on the function body's inner SELECT with `z=0,x=0,y=0` substituted and confirm the `entity_aliases` subplan loops ≈ the kept row count, not ~20,000. Record the three lengths and timings in your report. Reference numbers measured on the dev DB on 2026-10-31 with this exact SQL: z0 937 features / 110 KB, z2/2/1 1,076 / 129 KB, z5/17/11 617 / 80 KB, about 0.1 s each with `jit = off` (0.8 s without). If you see much more than that, report the EXPLAIN output rather than redesigning.

- [ ] **Step 6: Commit** `feat(tiles): atlas_entities MVT function with rank-based per-century cap and ETag`

### Task 3: Martin service (dev + prod), Caddy route, env

**Files:**
- Create: `docker/martin/config.yaml`
- Modify: `docker/docker-compose.yml` (new `martin` service after `redis`), `docker/docker-compose.prod.yml` (new `martin` service; `caddy.depends_on` adds `martin`; `web-build.environment` passes `VITE_MAP_TILES_URL`), `docker/Caddyfile` (`/tiles/*` on `APP_DOMAIN`), `.env.example` (`FORWARD_MARTIN_PORT=3000`), `docker/.env.prod.example` (`VITE_MAP_TILES_URL=https://api.example.org/tiles` under the SPA build section)
- Modify (docs, short): `docs/implementation-docs/setup.md` §2 service table + §3 commands; `CLAUDE.md` services list (add `martin`).

- [ ] **Step 1: Write `docker/martin/config.yaml`:**

```yaml
# Martin vector-tile server (dev and prod). Publishes only the tile functions
# in the `tiles` schema (see docs/schemas/atlas-tiles.md). D9 of the spec.
listen_addresses: '0.0.0.0:3000'
route_prefix: /tiles          # NOT base_path: base_path only rewrites TileJSON URLs (verified on 1.16.1)
cache_size_mb: 128
postgres:
  connection_string: ${MARTIN_DATABASE_URL}
  pool_size: 10
  auto_publish:
    tables: false
    functions:
      from_schemas: [tiles]
```

  Martin 1.16 substitutes `${VAR}` in the config file (verified 2026-10-31 against the dev DB: Postgres 16.9, PostGIS 3.5.2). The variable is deliberately not named `DATABASE_URL`: Martin logs a deprecation warning whenever that exact name is set, even when the config substitutes it. Confirm in the probe that the custom name is substituted (the startup log prints the host it connects to); if not, fall back to `DATABASE_URL` and accept the warning.

- [ ] **Step 2: Add the dev service** to `docker/docker-compose.yml`:

```yaml
  martin:
    image: ghcr.io/maplibre/martin:1.16.1
    command: ['--config', '/config/martin.yaml']
    ports:
      - '${FORWARD_MARTIN_PORT:-3000}:3000'
    environment:
      MARTIN_DATABASE_URL: 'postgresql://${POSTGRES_USER:-history-mapped}:${POSTGRES_PASSWORD:-secret}@db:5432/${POSTGRES_DB:-history-mapped}'
    volumes:
      - ./martin/config.yaml:/config/martin.yaml:ro
    depends_on:
      db:
        condition: service_healthy
```

  Prod (`docker-compose.prod.yml`), same shape but `restart: unless-stopped`, no `ports:` (use `expose: ["3000"]`), and `MARTIN_DATABASE_URL: "postgresql://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST:-db}:${DB_PORT:-5432}/${DB_DATABASE}"`. Add `martin` to `caddy.depends_on`. In `docker/.env.prod.example`, next to `DB_PASSWORD`, add the comment `# Also interpolated into Martin's connection URL: keep it URL-safe (letters, digits, - _ . ~) or percent-encode it.` In `web-build.environment` add `VITE_MAP_TILES_URL: "${VITE_MAP_TILES_URL:-}"` so the SPA bundle gets the flag (D7).

- [ ] **Step 3: Probe Martin from the worktree config** (do not `docker compose up` the main project from the worktree). Use the one-off command from the working rules, then:
  - `curl -s http://localhost:3011/tiles/catalog` lists `atlas_entities`;
  - `curl -s http://localhost:3011/tiles/atlas_entities` (TileJSON) has `vector_layers[0].id == "entities"` (this comes from the function comment added in Task 2; Martin's own TileJSON for a function has no `vector_layers`);
  - `curl -sI http://localhost:3011/tiles/atlas_entities/0/0/0` returns 200 with an `etag` header, and `-H 'Origin: http://localhost:5173'` returns `access-control-allow-origin` (Martin enables CORS by default; if the header is missing, add a `cors:` section per the Martin 1.16 configuration docs and re-probe). `curl -sI http://localhost:3011/catalog` must be 404 and `/tiles/catalog` 200, proving the prefix.
  Stop the container afterwards.

- [ ] **Step 4: Caddy.** In `docker/Caddyfile`, inside the `{$APP_DOMAIN}` block, before the generic `handle`:

```
	# Vector tiles for the public atlas (Martin). Tiles are immutable per deploy.
	@tiles path /tiles/*
	handle @tiles {
		header Cache-Control "public, max-age=300"
		reverse_proxy martin:3000
	}
```

  Validate the file: `docker run --rm -v $WT/docker/Caddyfile:/etc/caddy/Caddyfile:ro -e APP_DOMAIN=a.example -e WEB_DOMAIN=b.example caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile`.

- [ ] **Step 5: Env + docs.** Add the two env lines; in `setup.md` add `martin` (`:3000`, "vector tiles for the public SPA, `/tiles/atlas_entities`") to the service table and a one-line "tiles" entry to the day-to-day commands, plus the note that **Martin discovers functions only at startup**: after running the `tiles` migrations against an already-running stack, `docker compose … restart martin`; in `CLAUDE.md` add `martin` to the Services sentence and `:3000` to the dev URLs line.

- [ ] **Step 6: Commit** `feat(docker): Martin tile server for the atlas (dev + prod, Caddy /tiles route)`

---

## Phase 2 — Identity rules, resolver, and the OHM-links backfill

### Task 4: `App\Support\OhmDate` (year, decdate, signed-id rules)

**Files:**
- Create: `api/app/Support/OhmDate.php`
- Test: `api/tests/Unit/Support/OhmDateTest.php`

Context: D2 and D3 need the same rules in PHP for the importer (Task 7) and the resolver (Task 5). Keep it a `final class` with static methods and no dependencies.

- [ ] **Step 1: Write the failing tests** (PHPUnit data providers):
  - `yearToDecdate(1900, 'start') === 1900.00137`, `yearToDecdate(1950, 'end') === 1950.99863`, `yearToDecdate(-2999, 'start') === -2998.99863`, `yearToDecdate(-2799, 'end') === -2798.00137` (compare with `assertEqualsWithDelta(…, 1e-9)`); invalid bound throws `InvalidArgumentException`.
  - `yearFromDate('-0027-01-16') === -27`, `'0476-09-04' → 476`, `'1453' → 1453`, `'1800-01-01' → 1800`, `'' → null`, `null → null`, `'c. 1200' → null`, `' 1066 ' → 1066`.
  - `yearsFrom('1900', '1950') === [1900, 1950]`, `yearsFrom(null, '1950') === [null, 1950]`.
  - `signedOsmId('relation', '1880') === -1880`, `('node','42') === 42`, `('way','7') === 7`, `('qid','Q1') === null`, `('relation','abc') === null`.
  - `externalTypesForSignedId(-1880) === ['types' => ['relation'], 'id' => '1880']`, `(42) === ['types' => ['node', 'way'], 'id' => '42']`, `(0)` throws `InvalidArgumentException`.

- [ ] **Step 2: Run → FAIL**: `$PHP php artisan test --filter=OhmDateTest`

- [ ] **Step 3: Implement** (`declare(strict_types=1); namespace App\Support;`):

```php
final class OhmDate
{
    public const START_OFFSET = 0.00137;
    public const END_OFFSET = 0.99863;

    public static function yearToDecdate(int $year, string $bound): float
    {
        return match ($bound) {
            'start' => $year + self::START_OFFSET,
            'end' => $year + self::END_OFFSET,
            default => throw new \InvalidArgumentException("bound must be 'start' or 'end', got '{$bound}'"),
        };
    }

    /** Signed year part of an OHM ISO-8601 date ('-0027-01-16' → -27). Null when absent or unparseable. */
    public static function yearFromDate(?string $date): ?int
    {
        if ($date === null || preg_match('/^\s*(-?\d{1,6})(?:-\d{2}(?:-\d{2})?)?\s*$/', $date, $m) !== 1) {
            return null;
        }
        return (int) $m[1];
    }

    /** @return array{0: ?int, 1: ?int} [start_year, end_year] (inclusive end; see spec D2) */
    public static function yearsFrom(?string $start, ?string $end): array
    {
        return [self::yearFromDate($start), self::yearFromDate($end)];
    }

    public static function signedOsmId(string $externalType, string $externalId): ?int
    {
        if (preg_match('/^\d{1,18}$/', $externalId) !== 1) {
            return null;
        }
        return match ($externalType) {
            'relation' => -(int) $externalId,
            'node', 'way' => (int) $externalId,
            default => null,
        };
    }

    /** @return array{types: list<string>, id: string} */
    public static function externalTypesForSignedId(int $osmId): array
    {
        if ($osmId === 0) {
            throw new \InvalidArgumentException('osm_id must be non-zero');
        }
        return $osmId < 0
            ? ['types' => ['relation'], 'id' => (string) -$osmId]
            : ['types' => ['node', 'way'], 'id' => (string) $osmId];
    }
}
```

- [ ] **Step 4: Run → PASS**; Pint.
- [ ] **Step 5: Commit** `feat(api): OhmDate rules for OHM decimal dates and signed OSM ids`

### Task 5: Resolver accepts a signed `osm_id`

**Files:**
- Modify: `api/app/Http/Api/V1/Requests/ResolveOhmFeatureRequest.php`, `api/app/Actions/EntityGeoRef/ResolveOhmFeatureAction.php`
- Test: `api/tests/Feature/Api/ResolveOhmFeatureSignedIdTest.php`
- Read first: `api/tests/Feature/Api/ResolveOhmFeaturePublicApiTest.php` (seeding + route usage), `api/app/Http/Api/V1/Controllers/MapResolutionController.php`.

Context: OHM tiles only carry a signed `osm_id` (spec §1). Both the public `GET /api/v1/map/resolve-ohm-feature` and the editorial `POST` use the same request class and action. The existing `provider/external_type/external_id` form must keep working.

- [ ] **Step 1: Write the failing tests** (public GET, seeding like `ResolveOhmFeaturePublicApiTest`; declare `use RefreshDatabase;`):
  1. `osm_id=-1880&provider=ohm&target_year=117` resolves an entity whose active ref is `relation/1880`.
  2. `osm_id=42` resolves a `node/42` ref.
  3. `osm_id=42` resolves a `way/42` ref when no node ref with that id exists.
  4. When both `node/42` and `way/42` refs exist on different entities, `osm_id=42` returns the node one (preference order).
  5. `osm_id=0` → 422; `osm_id` together with `external_id` → 422 (`prohibits`).
  6. Omitting both `osm_id` and `external_id` → 422.

- [ ] **Step 2: Run → FAIL**.

- [ ] **Step 3: Implement.** Request rules: `external_type` → `['required_without:osm_id', 'string', Rule::enum(…)]`, `external_id` → `['required_without:osm_id', 'string', 'max:255', 'prohibits:osm_id']`, add `'osm_id' => ['required_without:external_id', 'integer', 'not_in:0']`. In the action, before the query: if `isset($payload['osm_id'])`, `$ref = OhmDate::externalTypesForSignedId((int) $payload['osm_id']);` and use `->whereIn('gr.external_type', $ref['types'])->where('gr.external_id', $ref['id'])` plus a leading `->orderByRaw("CASE gr.external_type::text WHEN 'node' THEN 0 WHEN 'way' THEN 1 ELSE 2 END")`; otherwise keep the current two `where`s. The rest of the action (geometry lookup, `buildResponse`) is unchanged; `feature_ref.external_type` in the response must reflect the **matched** ref (read it from `$geoRef`, which it already does — verify).

- [ ] **Step 4: Run → PASS**, plus `--filter=ResolveOhmFeature` for the existing tests; Pint.
- [ ] **Step 5: Commit** `feat(api): resolve OHM features by signed osm_id (relation < 0, node/way > 0)`

### Task 6: Pipeline `ohm_links` — Overpass tags-only extraction

**Files:**
- Create: `pipeline/ohm_links/__init__.py`, `pipeline/ohm_links/fetcher.py`, `pipeline/ohm_links/records.py`, `pipeline/ohm_links/writer.py`, `pipeline/ohm_links/__main__.py`
- Modify: `pipeline/__main__.py` (register the group: `from pipeline.ohm_links.__main__ import cli as ohm_links_cli` … `cli.add_command(ohm_links_cli, name="ohm-links")`)
- Test: `pipeline/tests/test_ohm_links_records.py`, `pipeline/tests/test_ohm_links_fetcher.py`, `pipeline/tests/test_ohm_links_writer.py`
- Read first: `pipeline/ohm_borders/fetcher.py` (reuse `OVERPASS_URL`, the `requests.post(..., data={"data": query}, timeout=1800)` pattern), `pipeline/ohm_borders/__main__.py` (click + rich conventions), `pipeline/tests/test_ohm_borders_fetcher.py` (fixture style).

Context: D6. No geometry is fetched; `out tags;` keeps payloads small. Output is one JSONL file per run under `output/ohm_links/<run_id>/ohm_links.jsonl` plus `manifest.json`.

**Record contract** (one JSON object per line; this is also what Task 7 reads):

```json
{"osm_type": "relation", "osm_id": 1880, "wikidata_id": "Q2277", "name": "Imperium Romanum",
 "name_en": "Roman Empire", "admin_level": 2, "place": null,
 "start_date": "-0027-01-16", "end_date": "0476-09-04",
 "tags": {"boundary": "administrative", "admin_level": "2", "name": "…", "name:en": "…", "wikidata": "Q2277", "wikipedia": "…", "start_date": "…", "end_date": "…", "place": null}}
```

`tags` keeps only `TAG_KEYS = ("boundary", "admin_level", "type", "place", "name", "name:en", "official_name", "wikidata", "wikipedia", "start_date", "end_date")` that are present. `wikidata_id` is the `wikidata` tag when it matches `^Q\d+$`, else `null`. `admin_level` is an int or `null`.

- [ ] **Step 1: Write the failing tests.**
  - `records.py`: `element_to_record` maps a relation/node element fixture to the contract above; returns `None` for elements without `tags`; invalid `wikidata` tag → `wikidata_id None`; non-numeric `admin_level` → `None`.
  - `fetcher.py`: `BOUNDARIES_QUERY` and `PLACES_WITH_WIKIDATA_QUERY` are the strings below; `ids_queries(ids: list[tuple[str,int]], batch_size=500)` yields queries of the form `[out:json][timeout:600];(node(id:1,2);way(id:3);relation(id:4););out tags;` grouped by type, at most `batch_size` ids each; `fetch_elements(query, post=requests.post)` posts to `OVERPASS_URL` and returns `payload["elements"]` (test with a stub `post`).
  - `writer.py`: `write_records(records, path)` writes JSONL, de-duplicates by `(osm_type, osm_id)` keeping the first, returns counts; `write_manifest(path, run_id, counts)`.

- [ ] **Step 2: Run → FAIL**: `cd $WT && uv run --with pytest pytest pipeline/tests/test_ohm_links_records.py pipeline/tests/test_ohm_links_fetcher.py pipeline/tests/test_ohm_links_writer.py -q`

- [ ] **Step 3: Implement.** Queries:

```python
BOUNDARIES_QUERY = '[out:json][timeout:1800];relation["boundary"="administrative"];out tags;'
PLACES_WITH_WIKIDATA_QUERY = (
    '[out:json][timeout:1800];('
    'node["place"]["wikidata"];way["place"]["wikidata"];relation["place"]["wikidata"];'
    ');out tags;'
)
```

  CLI (`python -m pipeline ohm-links fetch`): options `--run-id` (default `datetime.utcnow().strftime("%Y%m%d-%H%M")`), `--out-dir` (default `output/ohm_links`), `--skip-boundaries`, `--skip-places`, `--ids-file PATH` (text, one `type/id` per line, as written by Task 7's export command). It runs the selected queries, concatenates elements, writes `ohm_links.jsonl` + `manifest.json`, prints counts with rich. Logging via the existing `_configure_logging` pattern.

- [ ] **Step 4: Run → PASS**; `uv run ruff check pipeline/ohm_links` if ruff is configured in `pyproject.toml` (skip if not).
- [ ] **Step 5: Commit** `feat(pipeline): ohm-links fetch — Overpass tags-only extraction of boundaries and places`

### Task 7: `pipeline:export-ohm-ref-ids` and `pipeline:import-ohm-links`

**Files:**
- Create: `api/app/Console/Commands/ExportOhmRefIdsCommand.php`, `api/app/Console/Commands/ImportOhmLinksCommand.php`, `api/app/Actions/EntityGeoRef/ImportOhmLinksAction.php`
- Test: `api/tests/Feature/Console/ExportOhmRefIdsTest.php`, `api/tests/Feature/Console/ImportOhmLinksTest.php` (both declare `use RefreshDatabase;`)
- Read first: `api/app/Console/Commands/ImportBordersCommand.php` (JSONL reading + batch id), `api/app/Jobs/ImportBorderEntityJob.php:181-215` (creating an OHM ref via `CreateEntityGeoRefAction`, the enum classes), `api/app/Actions/EntityGeoRef/CreateEntityGeoRefAction.php` (**it deactivates the entity's active primary of any provider when asked for a primary**), `api/database/factories/EntityGeoRefFactory.php`, the constraints in `api/database/migrations/2026_03_29_000001_create_entity_geo_refs_table.php` (`egr_valid_year_range`, the unique index on `(entity_id, provider, external_type, external_id)` which **includes inactive rows**).

Context: D6. The importer reads the whole JSONL into memory first (tens of thousands of small records) so that records sharing a Wikidata id can be ranked together, then applies these rules:

1. **Years.** `[$startYear, $endYear] = OhmDate::yearsFrom(start_date, end_date)`. If both are set and `start > end` (OHM has such data, e.g. relation/2851494 `1947→1600`), store **neither** year (the `egr_valid_year_range` check would reject the row), keep the raw strings, and count `invalid_years`.
2. **Existing refs** (`provider = ohm`, same `external_type` + `external_id`, any entity, **active or not**): set `temporal_start_year`/`temporal_end_year` when both are null (always when `--overwrite-years`); set `temporal_start`/`temporal_end` to the raw OHM strings when null; set `external_tags` to `$record['tags']` when null **or empty** (`[]`/`{}` — every current ref has a non-null value, 159 of them empty). Count `refs_updated` once per ref actually changed.
3. **QID links.** For each `wikidata_id`, gather its records and every `Entity` with that exact `wikidata_id`. For each such entity: skip records that already have a ref on this entity (any `is_active`, because of the unique index; count `skipped_existing` — never re-activate what an editor deactivated). Order the remaining records deterministically: `relation` before `way` before `node`; then the record whose `[start_year, end_year]` overlaps the entity's primary temporal range the most (treat null bounds as open); then the latest `end_date`; then lowest `osm_id`. The first record becomes `primary` **only if the entity has no active primary geo-ref of any provider** (`entities.primary_geo_ref_id IS NULL` and no row with `match_role = primary AND is_active`); every other record becomes `candidate`. Create through `CreateEntityGeoRefAction` with `retrieval_method overpass`, `match_score 0.9`, the years/raw dates/tags from rule 1, `source_meta = ['source' => 'ohm-links', 'batch_id' => $batchId, 'run_id' => basename(dirname($path))]`. Count `refs_created`; when a QID matches more than one entity count `qid_duplicates` once and log the entity ids.
4. Records that touched nothing count as `unmatched`.

`--dry-run` wraps everything in `DB::transaction` and rolls back at the end, printing the same counters. The command prints a counters table (`records`, `refs_updated`, `refs_created`, `skipped_existing`, `invalid_years`, `qid_duplicates`, `unmatched`) and returns 0.

`pipeline:export-ohm-ref-ids {path}` writes sorted, distinct `external_type/external_id` lines for all `entity_geo_refs` with `provider = 'ohm'` and a numeric id (feeds Task 6's `--ids-file`).

- [ ] **Step 1: Write the failing tests** (`Entity::factory()`, `EntityGeoRef::factory()`; seed `external_tags => null` explicitly where a test checks tag filling; write the JSONL fixture under `storage/framework/testing/` or `sys_get_temp_dir()`):
  - export: refs `relation/1880`, `node/42` and a `wikidata` ref → file has exactly `node/42` and `relation/1880`, sorted, no duplicates.
  - import: (a) an existing `relation/1880` ref (inactive is fine) gets years `-27`/`476`, raw dates and tags; (b) an entity with `wikidata_id Q2277` and no refs gets a **primary** `relation/1880` ref and `entities.primary_geo_ref_id` points at it; (c) an entity with an existing active primary ref (seed one with provider `wikidata`) gets a **candidate**, the existing primary stays active and remains `primary_geo_ref_id`; (d) two entities share a QID → both get refs and `qid_duplicates == 1`; (e) `--dry-run` leaves the `entity_geo_refs` count unchanged but reports `refs_created 1`; (f) a record with no QID and no existing ref → `unmatched 1`; (g) `--overwrite-years` replaces non-null years, the default does not; (h) `start_date 1947`, `end_date 1600` → both year columns stay null, raw strings stored, `invalid_years 1`; (i) an entity already holding an **inactive** ref for the record's id gets nothing new and `skipped_existing 1`; (j) three records with one QID (`node/1` 1700–1900, `relation/5` 1780–1850, `relation/9` 1890–1950) on one entity whose primary temporal range is 1800–1900 → `relation/5` is primary (relations before nodes; overlap 50 years beats relation/9's 10), the others candidates.

- [ ] **Step 2: Run → FAIL**: `$PHP php artisan test --filter='ImportOhmLinks|ExportOhmRefIds'`
- [ ] **Step 3: Implement** the action (`__invoke(string $path, string $batchId, bool $dryRun, bool $overwriteYears): array` returning the counters) and the two thin commands. Use the `GeoRefProvider`, `GeoRefExternalType`, `GeoRefMatchRole`, `GeoRefRetrievalMethod` enums as `ImportBorderEntityJob` does.
- [ ] **Step 4: Run → PASS**; Pint.
- [ ] **Step 5: Commit** `feat(api): import OHM links — fill geo-ref temporal ranges and create refs by Wikidata id`

---

## Phase 3 — SPA: tiles, resolution, correlation

### Task 8: `yearToDecdate` and an exported decimal date range

**Files:**
- Modify: `web/src/lib/ohm-date.ts`, `web/src/lib/ohm-layer-date-filter.ts`
- Test: `web/src/lib/ohm-date.test.ts` (new), `web/src/lib/ohm-layer-date-filter.test.ts` (new)

Context: D2. The SPA needs the same decdate rule as SQL/PHP, and Task 9 needs the decimal range the existing filter computes internally (`dateRangeFromInput`, currently module-private) to build the filter for **our** layers without touching the OHM-layer cache logic.

- [ ] **Step 1: Write the failing tests.** `yearToDecdate(1900, 'start') === 1900.00137`, `(1950, 'end') === 1950.99863`, `(-2999, 'start') === -2998.99863`, `(-2799, 'end') === -2798.00137` (`toBeCloseTo(…, 5)`). `ohmDateRange('1066')` returns `{ startDecimalDate ≈ 1066.0, endDecimalDate ≈ 1067.0 }` (whole-year input spans the year); `ohmDateRange(null)` returns `null`; `ohmDateRange({ start: '1000', end: '1100' })` spans both.
- [ ] **Step 2: Run → FAIL**: `$WEB pnpm --filter @history-mapped/web exec vitest run src/lib/ohm-date.test.ts src/lib/ohm-layer-date-filter.test.ts`
- [ ] **Step 3: Implement.** In `ohm-date.ts`:

```ts
export const DECDATE_START_OFFSET = 0.00137;
export const DECDATE_END_OFFSET = 0.99863;
/** OHM decimal-date convention for a year-only date (spec D2); mirrors tiles.year_to_decdate. */
export function yearToDecdate(year: number, bound: 'start' | 'end'): number {
    return year + (bound === 'start' ? DECDATE_START_OFFSET : DECDATE_END_OFFSET);
}
```

  In `ohm-layer-date-filter.ts`: export `dateRangeFromInput` under the name `ohmDateRange` (`export function ohmDateRange(input: OhmDateFilterInput): DateRange | null` wrapping the existing private function; export the `DateRange` type). No behaviour change for `applyOhmLayerDateFilter`.
- [ ] **Step 4: Run → PASS**; `$WEB pnpm --filter @history-mapped/web lint` and `types:check`.
- [ ] **Step 5: Commit** `feat(web): yearToDecdate and exported OHM date range helper`

### Task 9: Tile mode for the entity overlay (`VITE_MAP_TILES_URL`)

**Files:**
- Create: `web/src/lib/map-tiles.ts`, `web/src/lib/map-tiles.test.ts`
- Modify: `web/src/components/map/MapCanvas.tsx`, `web/src/hooks/useEntitiesInView.ts`, `web/src/lib/schemas/map.ts`, `web/vite.config.ts`, `web/.env.example`
- Read first: `MapCanvas.tsx` whole file; `web/src/hooks/useFilters.ts` (`groups`); `web/src/types/atlas.ts` (`ENTITY_GROUPS`); `web/src/lib/api/params.ts` (how groups become UPPERCASE); spec D1, D7, D8.

Context: with tiles, the three entity layers read a vector source instead of GeoJSON; the year filter and the group filter become **client-side filter expressions on our layers**, owned by one builder in `map-tiles.ts` (the OHM-layer date filter is untouched). Another session is editing `MapCanvas.tsx` in the main checkout; keep edits here minimal and localised.

- [ ] **Step 1: Write the failing tests** for `map-tiles.ts` (pure functions; stub `import.meta.env` via `vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles')`):
  - `isMapTilesEnabled()` false when unset, true when set; `entityTileSource()` returns `{ type: 'vector', tiles: ['http://t/tiles/atlas_entities/{z}/{x}/{y}'], minzoom: 0, maxzoom: 14 }` (trailing slash on the env value is stripped). Read `import.meta.env.VITE_MAP_TILES_URL` **inside** the functions, not in a module-level constant, so `vi.stubEnv` works.
  - `entityLayerFilter({ geometry: 'point', time: { kind: 'instant', year: 1066 }, groups: [] })` returns `['all', <geometry filter>, <date window>]` where the date window is `['all', ['<=', ['to-number', ['get','start_decdate']], 1067.0], ['any', ['!', ['has','end_decdate']], ['>=', ['to-number', ['get','end_decdate']], 1066.0]]]` built from `ohmDateRange(yearToOhmDate(1066))`; with `groups: ['polity']` it adds `['in', ['get','entity_group'], ['literal', ['POLITY']]]`; with all groups selected it adds nothing; with a range `time` it passes `{ start, end }` to `ohmDateRange`. `time` is the `TimeState` from `web/src/types/atlas.ts`.

- [ ] **Step 2: Run → FAIL**.

- [ ] **Step 3: Implement `map-tiles.ts`:** `MAP_TILES_URL`, `isMapTilesEnabled()`, `ENTITY_SOURCE_LAYER = 'entities'`, `entityTileSource()`, `entityLayerFilter(opts)` (uses `yearToOhmDate` + `ohmDateRange`), and `applyEntityLayerFilters(map, { layers: { fill, line, symbol }, time, groups })` that calls `map.setFilter` for each layer when `map.getLayer(id)` exists.

- [ ] **Step 4: Wire `MapCanvas.tsx`:**
  - `addEntityLayers`: when `isMapTilesEnabled()`, `map.addSource(SOURCE_ID, entityTileSource())` and add `'source-layer': ENTITY_SOURCE_LAYER` to the three layer specs; otherwise unchanged GeoJSON. Extract the two filters (`isPolygon`, `isPoint`) so the filter builder can reuse them (export them from `map-tiles.ts` instead of defining inline).
  - After the layers are added and whenever `time` or `groups` change (new effect, tiles only): `applyEntityLayerFilters(map, …)`. Keep the existing `applyOhmLayerDateFilter(map, yearToOhmDate(year))` call for the OHM layers.
  - The "push entity data" effect returns early in tile mode. `useEntitiesInView` gets `enabled: ready && !isMapTilesEnabled()` (import the flag; hooks must stay pure, no map access).
  - `MapFeatureProperties` in `schemas/map.ts`: add optional `display_priority?: number | null; ohm_osm_id?: number | null; start_decdate?: number; end_decdate?: number;` with a comment that tile features carry these (and their `feature.id` is the stable `fid`, which is **not** a property) while REST features carry `ohm_external_*`.
  - `vite.config.ts`: add a `runtimeCaching` rule before the API rule: `urlPattern: /\/tiles\/atlas_entities\//i`, `handler: 'StaleWhileRevalidate'`, `cacheName: 'atlas-tiles'`, `expiration: { maxEntries: 2000, maxAgeSeconds: DAY_SECONDS }`, `cacheableResponse: { statuses: [0, 200] }`.
  - `web/.env.example`: add, **commented out** so REST stays the default (D7): `# Optional: Martin tile endpoint; unset = GeoJSON viewport queries` / `# VITE_MAP_TILES_URL=http://localhost:3000/tiles`.

- [ ] **Step 5: Run → PASS**; lint; types:check; full `vitest run`.

- [ ] **Step 6: Manual verification** with the "manual verification stack" from the working rules (worktree API on :8011, Martin on :3011, SPA on :5175; Task 2's migration applied). Open `http://localhost:5175`, confirm: markers render from `/tiles/atlas_entities/…` requests; scrubbing the timeline issues **no** `/entities/map` requests and markers change; the Layers group toggles filter markers; switching basemap keeps the overlay. Record what you saw in the report. Stop the containers.

- [ ] **Step 7: Commit** `feat(web): entity overlay from Martin vector tiles behind VITE_MAP_TILES_URL`

### Task 10: Click resolution by signed `osm_id`, local tile lookup first

**Files:**
- Modify: `web/src/lib/ohm-resolve.ts`
- Test: `web/src/lib/ohm-resolve.test.ts` (new)
- Read first: spec §1 table, D3; Task 5's API change (`osm_id` query param).

- [ ] **Step 1: Write the failing tests** (export the pure helpers):
  - `extractIdentity({ osm_id: -1880 })` → `{ osm_id: -1880 }`; `({ osm_id: 42 })` → `{ osm_id: 42 }`; `({ '@id': 'relation/1880' })` → `{ osm_id: -1880 }`; `({ osm_type: 'node', osm_id: 42 })` → `{ osm_id: 42 }`; `({ osm_id: 0 })` and `({})` → `null`.
  - `pickFeatureForYear(features, 1066)` returns the feature whose `[start_decdate, end_decdate]` window contains `yearToDecdate(1066, 'start')`, treating a missing `end_decdate` as open-ended, else `null`.

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement.** Identity becomes `{ osm_id: number }` (signed). `resolveIdentity` sends `{ provider: 'ohm', osm_id, target_year }`. Before the network: when `isMapTilesEnabled()`, `map.querySourceFeatures(SOURCE_ID, { sourceLayer: ENTITY_SOURCE_LAYER, filter: ['==', ['get', 'ohm_osm_id'], osm_id] })` → `pickFeatureForYear` → return its `properties.id` without a request. Keep `MAX_CANDIDATES`, `HIT_RADIUS_PX`, the layer selection and the sequencing as they are. Export `SOURCE_ID`/`ENTITY_SOURCE_LAYER` from `map-tiles.ts` if `MapCanvas.tsx` still defines `SOURCE_ID` locally, and import it there, so there is one definition.
- [ ] **Step 4: Run → PASS**; lint; types:check.
- [ ] **Step 5: Manual check** (manual verification stack from the working rules): pick a linked entity that is actually in the tiles — `SELECT e.name, egr.external_id, ST_AsText(gp.geom) FROM entity_geo_refs egr JOIN entities e USING (entity_id) JOIN geometry_periods gp USING (entity_id) WHERE egr.provider='ohm' AND egr.external_type='relation' AND egr.is_active LIMIT 5` (only ~62 OHM-linked entities have a geometry period before Task 12) — centre the map on it at the right year and click the OHM polity **label** (not a boundary line) → the entity opens.
- [ ] **Step 6: Commit** `fix(web): resolve OHM basemap clicks by signed osm_id, tile-local first`

### Task 11: Correlation highlight (labels, polygons, two-way hover)

**Files:**
- Modify: `web/src/lib/map-config.ts`, `web/src/components/map/MapCanvas.tsx`, `web/src/components/atlas/BrowseTab.tsx`
- Create: `web/src/lib/ohm-highlight.ts`, `web/src/lib/ohm-highlight.test.ts`
- Read first: spec D5; `web/src/stores/ephemeral.ts` and `web/src/hooks/ephemeral.ts` (`useHover` → `{ hoverId, setHover }` exists but **nothing writes or reads it yet**); `web/src/hooks/useSelection.ts`; `BrowseTab.tsx` (`ListRow` only prefetches on `onMouseEnter`); MapLibre docs on `promoteId` and `setFeatureState`.

Context: three things must land together: the OHM-side highlight (labels + lazily shown polygons), the hover plumbing that nothing has wired yet (list rows and markers write `hoverId`; list rows and markers read it), and the two-way link between them through the osm-id index. `ohm_admin` layers are not date-filtered (the date filter only touches `source === 'ohm'`); that is fine because they are keyed by id and only shown for the hovered/selected feature.

- [ ] **Step 1: Write the failing tests** for pure helpers in `ohm-highlight.ts`:
  - `linkIndexFromFeatures(features)` builds `Map<number, string>` (signed osm id → entity id) from tile-shaped features (`ohm_osm_id`) **and** REST-shaped ones (`ohm_external_type` + `ohm_external_id`, relation → negative); ignores features without a link.
  - `diffLinkedState(prev: Set<number>, next: Set<number>)` returns `{ add: number[], remove: number[] }`.
  - `applyEmphasis(fakeMap, { hoverOsmId: -1880, selectedOsmId: null }, prevState)` calls `setFeatureState({ source: 'ohm_admin', sourceLayer: 'boundaries', id: -1880 }, { hover: true })` and sets both `ohm-admin-*` layers' `visibility` to `visible`; a second call with both null removes the state and hides the layers. Use a fake map object recording calls (`setFeatureState`, `removeFeatureState`, `setLayoutProperty`, `getLayer`).

- [ ] **Step 2: Run → FAIL**.

- [ ] **Step 3: Implement the OHM side.**
  - `map-config.ts`: in the style normalisation, set `style.sources.ohm.promoteId = { land_ohm_centroids: 'osm_id' }` (only when the source exists); add `style.sources.ohm_admin = { type: 'vector', tiles: ['https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf'], minzoom: 2, maxzoom: 14, promoteId: 'osm_id', attribution: OHM_ATTRIBUTION }`; for every `symbol` layer whose `source-layer === 'land_ohm_centroids'`, wrap `paint['text-color']` as `['case', ['boolean', ['feature-state', 'linked'], false], LINK_COLOR, <original or '#2a2722'>]`. Export `OHM_ADMIN_SOURCE = 'ohm_admin'`, `OHM_ADMIN_LAYER = 'boundaries'`, `OHM_CENTROID_SOURCE_LAYER = 'land_ohm_centroids'`; `LINK_COLOR` (one readable accent such as `#b4552d`) lives in `ohm-highlight.ts` and is imported here.
  - `ohm-highlight.ts`: `addOhmAdminLayers(map, beforeId)` adds `ohm-admin-fill` (fill, `fill-color: LINK_COLOR`, `fill-opacity: ['case', ['boolean', ['feature-state','selected'], false], 0.22, ['boolean', ['feature-state','hover'], false], 0.12, 0]`) and `ohm-admin-line` (line width 2, opacity ladder 0.9 / 0.6 / 0), both `layout: { visibility: 'none' }`, inserted below the entity fill layer; `syncLinkedLabels(map, index, prev)` sets/removes `linked` on `{ source: 'ohm', sourceLayer: OHM_CENTROID_SOURCE_LAYER, id }`; `applyEmphasis(...)` as tested; `centroidLayerIds(map)`.

- [ ] **Step 4: Wire the hover plumbing** (new, nothing exists today):
  - `BrowseTab.tsx` `ListRow`: `const setHover = useEphemeralStore((s) => s.setHover);` `onMouseEnter={() => { prefetch(e.id); setHover(e.id); }}` `onMouseLeave={() => setHover(null)}`; add a visible hovered style when the row is the hovered one (reuse the row's existing active/selected styling tokens; do not invent new colours).
  - `MapCanvas.tsx`: `mousemove` on `SYMBOL_LAYER` → `setHover(properties.id)` (only when it changes), `mouseleave` → `setHover(null)`; `mousemove`/`mouseleave` on the centroid layer ids → when the feature's `state.linked` is true, `setHover(index.get(osm_id))`, and clear on leave only if this handler set it. Marker highlight from `hoverId` (works in tile and REST mode): a separate symbol layer `entities-hover` (`HOVER_LAYER`) on the same source/source-layer, same `icon-image` expression, `icon-size: 1.05`, `icon-allow-overlap: true`, no text, initial filter `['==', ['get','id'], '']`; the `hoverId` effect calls `map.setFilter(HOVER_LAYER, ['all', isPoint, ['==', ['get','id'], hoverId ?? '']])`. Do **not** use `feature-state` in `icon-size` or any other layout property — MapLibre rejects `feature-state` there (`"feature-state" data expressions are not supported with layout properties`) and the whole layer would fail to add; the group marker images are not SDF, so `icon-color`/`icon-halo-*` would not show either. Our symbol layer's `text-color` becomes `['case', ['!=', ['coalesce', ['get','ohm_osm_id'], ['get','ohm_external_id']], null], LINK_COLOR, '#2a2722']`.
  - `BrowseTab.tsx` row hover read: use a per-row selector `useEphemeralStore((s) => s.hoverId === e.id)` rather than `useHover()` in every row, so only the two affected rows re-render.
  - `MapCanvas.tsx` glue: after `addEntityLayers` on `style.load`, call `addOhmAdminLayers(map, FILL_LAYER)`; on `sourcedata` for `SOURCE_ID` (debounced 150 ms, only when `isSourceLoaded`) rebuild the index (`querySourceFeatures` in tile mode, `dataRef.current.features` in REST mode) and `syncLinkedLabels`; effects on `hoverId` and the selected id call `applyEmphasis` with the osm ids from the index.

- [ ] **Step 5: Run → PASS**; lint; types:check; full vitest.

- [ ] **Step 6: Manual verification** (manual verification stack; use an entity from Task 10 Step 5's query so it is in the tiles): with the network panel open, confirm **no** `ohm_admin` tile requests while nothing is hovered/selected; hover that polity in the Browse list → its marker grows, its OHM label turns `LINK_COLOR`, its polygon fills; select it → stronger fill; hover its OHM label on the map → the list row and marker highlight. If `ohm_admin` tiles load while the layers are hidden, switch `addOhmAdminLayers`/`applyEmphasis` to add/remove the layers instead of toggling visibility and say so in the report.

- [ ] **Step 7: Commit** `feat(web): highlight OHM labels and polygons linked to atlas entities; two-way hover`

---

## Phase 4 — Data run and documentation

### Task 12: Run the OHM-links backfill on the dev database

**Files:** none in the repo except a results note appended to `docs/implementation-docs/data-quality-runbook.md` (new section "OHM link backfill (2026-10-31)").

- [ ] **Step 1:** `$PHP php artisan migrate` (if not already), then `$PHP php artisan pipeline:export-ohm-ref-ids /var/www/html/../output/ohm_ref_ids.txt` — the `app` image mounts only `api/`, so write to `storage/app/ohm_ref_ids.txt` and copy it to `$WT/output/ohm_ref_ids.txt` on the host.
- [ ] **Step 2:** `cd $WT && uv run python -m pipeline ohm-links fetch --run-id 2026-10-31 --ids-file output/ohm_ref_ids.txt`. Expect minutes (Overpass, 1800 s timeout). Record element counts from `manifest.json`.
- [ ] **Step 3:** Dry run: copy the JSONL into `$WT/api/storage/app/ohm_links.jsonl` and run `$PHP php artisan pipeline:import-ohm-links storage/app/ohm_links.jsonl --dry-run`. Record counters. Then run without `--dry-run`.
- [ ] **Step 4:** Measure, via `docker compose -f /home/pickle/code/history-mapped/docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped`:
  - entities with an active OHM ref (was 3,305), polities linked to an OHM relation (was 766 / 17,515), OHM refs with `temporal_start_year` (was 0 / 3,305).
  - tile features that carry a link: `SELECT count(*) FROM tiles.atlas_entity_features WHERE ohm_osm_id IS NOT NULL` before and after (was ~62 before this plan: only 62 of the 3,305 OHM-linked entities have a geometry period).
  - the gap: `SELECT count(*) FROM entities e WHERE EXISTS (SELECT 1 FROM entity_geo_refs r WHERE r.entity_id = e.entity_id AND r.provider = 'ohm' AND r.is_active) AND NOT EXISTS (SELECT 1 FROM geometry_periods gp WHERE gp.entity_id = e.entity_id)` (3,243 on 2026-10-31) and how many of those have an `entity_locations` point **and** a primary temporal range. **Report only**: name the existing backfill path (`BackfillGeometryPeriodsAction` / its artisan command) that would give them a period; do not run it — that is a separate decision.
- [ ] **Step 5:** Append the numbers and the exact commands to the runbook section; commit `chore(data): OHM link backfill run 2026-10-31 (numbers in data-quality runbook)`. Do **not** commit anything under `output/` (it is ignored; check `git status`).

### Task 13: Documentation, contract, and parity check

**Files:**
- Create: `docs/schemas/atlas-tiles.md`
- Modify: `docs/schemas/README.md` (API section), `docs/architecture/ohm-integration.md` (status note at top: tiles + correlation live; §2.1 fix the General tileset path `maps/ohm`; §7.2 replace the hypothetical with the real Martin source; add a "Feature identity" subsection with the signed `osm_id` table from the spec), `docs/architecture/frontend-app.md` (tile mode paragraph), `docs/implementation-docs/deployment-runbook.md` (§4: `martin` service, `/tiles` route, `VITE_MAP_TILES_URL` in `.env.prod`, and that a deploy which adds tile functions must restart `martin` after `migrate` — the CI deploy script's `up -d` recreates it only when its image or config changed), `docs/plans/STATUS.md` (new row under the superpowers section: this plan, 🟡/✅ with what shipped), `CLAUDE.md` if Task 3 did not already add `martin`.

- [ ] **Step 1: Write `docs/schemas/atlas-tiles.md`** from spec §4: endpoints, source-layer, feature id (`feature.id`, not a property), the property table, the rank-based per-century cap, the decdate rule with the three implementations (`tiles.year_to_decdate`, `OhmDate::yearToDecdate`, `yearToDecdate`), caching/ETag behaviour, and the feature flag.
- [ ] **Step 2: Parity check.** Diff the property list of `MapEntitiesAction` (REST) against the view. If the REST projection gained properties since this plan was written (for example `has_map_story` from the concurrent battle-map branch), add them to the view and the tile function in a follow-up migration `2026_10_31_000003_…` and to the contract; otherwise record "parity confirmed" in the STATUS row.
- [ ] **Step 3:** Update the other docs as listed; keep each edit short and factual.
- [ ] **Step 4:** Run the whole verification set once more: `$PHP php artisan test`, `$WEB pnpm --filter @history-mapped/web test`, `$WEB … lint`, `$WEB … types:check`, `cd $WT && uv run --with pytest pytest pipeline/tests -q` (one pre-existing failure allowed, see working rules).
- [ ] **Step 5: Commit** `docs: atlas tile contract, OHM correlation notes, deployment and status updates`

---

## Out of scope (tracked elsewhere)

- OHM replica (imposm + Martin over the OHM planet): see the 2026-10-31 assessment; revisit when server-side joins or our own polygons inside OHM's layer schema are wanted.
- Read-only Postgres role for Martin (hardening).
- Admin app on tiles.
