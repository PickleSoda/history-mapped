<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * `tiles.atlas_entities(z, x, y)` — the MVT function Martin publishes as the
 * `atlas_entities` source (spec 2026-10-31 atlas tiles, D1/D4/D8).
 *
 * One `entities` layer built from `tiles.atlas_entity_features`. Density is a
 * rank-based cap per tile and per century of `start_year` (D4): curated
 * `display_priority` first, then `impact_score`. `key = md5(mvt)` becomes
 * Martin's ETag (D8). The JSON comment is merged into the TileJSON so that
 * `vector_layers` is advertised.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
CREATE OR REPLACE FUNCTION tiles.atlas_entities(z integer, x integer, y integer)
RETURNS TABLE (mvt bytea, key text)
LANGUAGE plpgsql STABLE STRICT PARALLEL SAFE
SET jit = off   -- the cost estimate triggers ~0.7 s of JIT compilation per call; ~0.1 s without it
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
SQL);
    }

    public function down(): void
    {
        DB::unprepared('DROP FUNCTION IF EXISTS tiles.atlas_entities(integer, integer, integer);');
    }
};
