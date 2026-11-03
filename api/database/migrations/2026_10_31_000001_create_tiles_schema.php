<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * The `tiles` schema that Martin publishes (spec 2026-10-31 atlas tiles).
 *
 * `tiles.atlas_entity_features` is the one feature view behind the atlas
 * vector tiles. It mirrors the REST projection in
 * App\Actions\Entity\MapEntitiesAction (primary-alias name, active OHM ref
 * primary first, verification-status list, EVENT ±10y padding, point geometry
 * for OHM-linked entities) but covers every period of all time, and adds OHM
 * decimal dates (D2) and the signed OSM id (D3).
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
CREATE SCHEMA IF NOT EXISTS tiles;

-- D2: OHM decimal-date convention for a year-only date.
CREATE OR REPLACE FUNCTION tiles.year_to_decdate(year integer, bound text)
RETURNS double precision LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
  SELECT CASE bound
    WHEN 'start' THEN year + 0.00137
    WHEN 'end'   THEN year + 0.99863
  END::double precision
$$;

-- D4: per-tile, per-century cap by rank (NULL = keep everything).
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
    WHEN external_id IS NULL OR external_id !~ '^[1-9][0-9]{0,17}$' THEN NULL  -- no zero ids (parity with OhmDate::signedOsmId)
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
SQL);
    }

    public function down(): void
    {
        DB::unprepared(<<<'SQL'
DROP VIEW IF EXISTS tiles.atlas_entity_features;
DROP FUNCTION IF EXISTS tiles.signed_osm_id(text, text);
DROP FUNCTION IF EXISTS tiles.simplify_tolerance(integer);
DROP FUNCTION IF EXISTS tiles.tile_cap_for_zoom(integer);
DROP FUNCTION IF EXISTS tiles.year_to_decdate(integer, text);
DROP SCHEMA IF EXISTS tiles CASCADE;
SQL);
    }
};
