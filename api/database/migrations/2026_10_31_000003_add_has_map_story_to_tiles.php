<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Tile/REST property parity: `has_map_story` (spec 2026-10-31 atlas tiles,
 * docs/schemas/atlas-tiles.md).
 *
 * App\Actions\Entity\MapEntitiesAction serves `has_map_story` (the entity has
 * a `map_stories` row; the SPA draws a battle-map marker for it). This adds the
 * same flag as the last column of `tiles.atlas_entity_features` and to the
 * SELECT list and TileJSON comment of `tiles.atlas_entities(z, x, y)`. The view
 * and function bodies are otherwise those of migrations 000001 and 000002.
 * Restart Martin afterwards so it picks up the new TileJSON comment.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
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
  CASE WHEN ohm.osm_id IS NOT NULL THEN gp.geom ELSE COALESCE(gp.territory_geom, gp.geom) END AS geom,
  -- Appended (CREATE OR REPLACE VIEW only adds columns at the end); parity with
  -- MapEntitiesAction's has_map_story.
  EXISTS (SELECT 1 FROM map_stories ms WHERE ms.entity_id = e.entity_id) AS has_map_story
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
      f.ohm_osm_id,
      f.has_map_story
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
'{"vector_layers":[{"id":"entities","fields":{"id":"String","name":"String","entity_type":"String","entity_group":"String","impact_score":"Number","display_priority":"Number","start_year":"Number","end_year":"Number","start_decdate":"Number","end_decdate":"Number","entity_color":"String","ohm_osm_id":"Number","has_map_story":"Boolean"}}]}';
SQL);
    }

    public function down(): void
    {
        // The 000002 function first (it must stop selecting the column), then
        // the 000001 view: CREATE OR REPLACE VIEW cannot drop a column.
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

DROP VIEW IF EXISTS tiles.atlas_entity_features;

CREATE VIEW tiles.atlas_entity_features AS
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
SQL);
    }
};
