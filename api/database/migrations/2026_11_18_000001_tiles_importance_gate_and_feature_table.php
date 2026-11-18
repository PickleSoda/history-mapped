<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Atlas tiles from a precomputed feature table, with an importance gate per
 * zoom (docs/schemas/atlas-tiles.md, "Density").
 *
 * Until now every tile ran `tiles.atlas_entity_features` (a view over
 * geometry_periods ⋈ entities with per-row alias and OHM subqueries) and ranked
 * every period in its envelope. With 641k entities on a 2 GB droplet, the z0
 * tile took 16 s cold: it read the 1 GB entities heap. And because the cap was
 * only per century, a world-view tile still carried over 1,000 features,
 * cities and monuments included.
 *
 *   - `tiles.feature_min_zoom(group, type, importance)`: the lowest zoom a
 *     feature appears at. Cities from z7 (z9 below importance 80), other
 *     places from z9 (z11 below 70); everything else from z0 at importance
 *     90+, then z3 / z5 / z7 / z9. Importance is GREATEST(display_priority,
 *     impact_score): a curated priority can raise a feature, never bury it.
 *   - `tiles.atlas_features`: a materialized copy of the view, plus `century`
 *     and `min_zoom`, about 15 MB. Refreshed by `php artisan tiles:refresh`,
 *     which the scheduler runs every five minutes and which skips the work
 *     when `tiles.change_seq` has not moved. Statement-level triggers on the
 *     five source tables bump that sequence.
 *   - `tiles.tile_cap_for_zoom`: smaller per-century caps (8 / 12 / 16 / 32 /
 *     64, none from z13).
 *   - `tiles.atlas_entities(z, x, y)` reads the table. Its output is
 *     unchanged.
 *
 * A data-only pg_dump carries no materialized view rows, so a content load
 * must run `tiles:refresh --force` afterwards.
 */
return new class extends Migration
{
    private const SOURCE_TABLES = ['geometry_periods', 'entities', 'entity_aliases', 'entity_geo_refs', 'map_stories'];

    public function up(): void
    {
        DB::unprepared(<<<'SQL'
CREATE OR REPLACE FUNCTION tiles.feature_min_zoom(entity_group text, entity_type text, importance integer)
RETURNS integer LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT CASE
    WHEN entity_type = 'city' THEN CASE WHEN COALESCE(importance, 0) >= 80 THEN 7 ELSE 9 END
    WHEN entity_group = 'PLACE' THEN CASE WHEN COALESCE(importance, 0) >= 70 THEN 9 ELSE 11 END
    WHEN COALESCE(importance, 0) >= 90 THEN 0
    WHEN importance >= 80 THEN 3
    WHEN importance >= 70 THEN 5
    WHEN importance >= 60 THEN 7
    ELSE 9
  END
$$;

CREATE OR REPLACE FUNCTION tiles.tile_cap_for_zoom(z integer)
RETURNS integer LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE WHEN z <= 1 THEN 8 WHEN z <= 3 THEN 12 WHEN z <= 6 THEN 16 WHEN z <= 9 THEN 32 WHEN z <= 12 THEN 64 END
$$;

-- Re-runnable: migrate:fresh drops the public tables (cascading to this view)
-- but leaves the sequence in the tiles schema.
DROP MATERIALIZED VIEW IF EXISTS tiles.atlas_features;
CREATE MATERIALIZED VIEW tiles.atlas_features AS
SELECT f.*,
       floor(f.start_year / 100.0)::integer AS century,
       tiles.feature_min_zoom(f.entity_group, f.entity_type, GREATEST(f.display_priority, f.impact_score)) AS min_zoom
FROM tiles.atlas_entity_features f
WITH DATA;

-- The unique index makes REFRESH ... CONCURRENTLY possible (tiles keep serving).
CREATE UNIQUE INDEX atlas_features_period_uidx ON tiles.atlas_features (geometry_period_id);
CREATE INDEX atlas_features_bbox_gist ON tiles.atlas_features USING gist (bbox_geom);

-- Change counter for tiles:refresh. nextval is non-transactional and takes no
-- row lock, so the statement triggers cost next to nothing.
CREATE SEQUENCE IF NOT EXISTS tiles.change_seq;

CREATE OR REPLACE FUNCTION tiles.note_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM nextval('tiles.change_seq');
  RETURN NULL;
END
$$;

CREATE OR REPLACE FUNCTION tiles.atlas_entities(z integer, x integer, y integer)
RETURNS TABLE (mvt bytea, key text)
LANGUAGE plpgsql STABLE STRICT PARALLEL SAFE
SET jit = off   -- the cost estimate triggers ~0.7 s of JIT compilation per call
AS $$
DECLARE
  env3857 geometry;
  env4326 geometry;
  cap     integer  := tiles.tile_cap_for_zoom(z);
  tol     double precision := tiles.simplify_tolerance(z);
  tile    bytea;
BEGIN
  -- Out-of-range coordinates (ST_TileEnvelope would raise, and Martin would
  -- answer 500): serve an empty tile instead.
  IF z < 0 OR z > 30 OR x < 0 OR y < 0 OR x >= (1::bigint << z) OR y >= (1::bigint << z) THEN
    mvt := ''::bytea;
    key := md5(mvt);
    RETURN NEXT;
    RETURN;
  END IF;

  env3857 := ST_TileEnvelope(z, x, y);
  env4326 := ST_Transform(env3857, 4326);

  SELECT ST_AsMVT(t, 'entities', 4096, 'geom', 'fid') INTO tile
  FROM (
    SELECT
      ST_AsMVTGeom(
        ST_Transform(
          CASE WHEN tol > 0 AND ST_Dimension(r.geom) > 0
               THEN ST_SimplifyPreserveTopology(r.geom, tol) ELSE r.geom END,
          3857),
        env3857, 4096, 64, true) AS geom,
      r.fid,
      r.id,
      r.name,
      r.entity_type,
      r.entity_group,
      r.impact_score,
      r.display_priority,
      r.start_year,
      r.end_year,
      r.start_decdate,
      r.end_decdate,
      r.entity_color,
      r.ohm_osm_id,
      r.has_map_story
    FROM (
      SELECT f.*,
             row_number() OVER (
               PARTITION BY f.century
               ORDER BY f.display_priority DESC NULLS LAST, f.impact_score DESC NULLS LAST, f.geometry_period_id
             ) AS rn
      FROM tiles.atlas_features f
      WHERE f.min_zoom <= z AND f.bbox_geom && env4326
    ) r
    WHERE cap IS NULL OR r.rn <= cap
  ) AS t
  WHERE t.geom IS NOT NULL;

  mvt := COALESCE(tile, ''::bytea);
  key := md5(mvt);
  RETURN NEXT;
END
$$;

COMMENT ON FUNCTION tiles.atlas_entities(integer, integer, integer) IS
'{"vector_layers":[{"id":"entities","fields":{"id":"String","name":"String","entity_type":"String","entity_group":"String","impact_score":"Number","display_priority":"Number","start_year":"Number","end_year":"Number","start_decdate":"Number","end_decdate":"Number","entity_color":"String","ohm_osm_id":"Number","has_map_story":"Boolean"}}]}';
SQL);

        foreach (self::SOURCE_TABLES as $table) {
            DB::unprepared("DROP TRIGGER IF EXISTS tiles_note_change ON public.{$table};");
            DB::unprepared(
                "CREATE TRIGGER tiles_note_change AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON public.{$table} "
                .'FOR EACH STATEMENT EXECUTE FUNCTION tiles.note_change();',
            );
        }
    }

    public function down(): void
    {
        foreach (self::SOURCE_TABLES as $table) {
            DB::unprepared("DROP TRIGGER IF EXISTS tiles_note_change ON public.{$table};");
        }

        DB::unprepared(<<<'SQL'
DROP MATERIALIZED VIEW IF EXISTS tiles.atlas_features;
DROP FUNCTION IF EXISTS tiles.note_change();
DROP SEQUENCE IF EXISTS tiles.change_seq;
DROP FUNCTION IF EXISTS tiles.feature_min_zoom(text, text, integer);

CREATE OR REPLACE FUNCTION tiles.tile_cap_for_zoom(z integer)
RETURNS integer LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE WHEN z <= 1 THEN 12 WHEN z <= 3 THEN 16 WHEN z <= 6 THEN 24 WHEN z <= 9 THEN 48 WHEN z <= 12 THEN 96 END
$$;
SQL);

        // The view-based tile function of 2026_10_31_000003 (its view is unchanged).
        (require __DIR__.'/2026_10_31_000003_add_has_map_story_to_tiles.php')->up();
    }
};
