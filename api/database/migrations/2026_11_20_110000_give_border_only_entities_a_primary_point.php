<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * An entity placed only by a geometry period of its own (an OHM import or a
 * hand-drawn one) gets that place as its primary point: a point inside the
 * period's shape. The map's search filter can then look in `entity_locations`
 * alone.
 *
 * A trigger keeps this true for every writer (Laravel imports, the Python
 * pipeline's SQL, content bundles). `derived` periods are left out: they put
 * an entity at a related entity's place, and a primary point is never a
 * borrowed coordinate.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
            CREATE OR REPLACE FUNCTION geometry_period_point(g geometry) RETURNS geometry
            LANGUAGE plpgsql IMMUTABLE AS $$
            BEGIN
                IF g IS NULL OR ST_IsEmpty(g) THEN
                    RETURN NULL;
                END IF;
                IF GeometryType(g) = 'POINT' THEN
                    RETURN g;
                END IF;
                RETURN ST_PointOnSurface(ST_MakeValid(g));
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL; -- a shape PostGIS cannot handle places nothing
            END $$;

            CREATE OR REPLACE FUNCTION set_primary_point_from_geometry_period() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
                pt geometry;
            BEGIN
                IF NEW.provenance_mode = 'derived' THEN
                    RETURN NEW;
                END IF;
                IF EXISTS (
                    SELECT 1 FROM entity_locations
                    WHERE entity_id = NEW.entity_id AND is_primary = true AND geom IS NOT NULL
                ) THEN
                    RETURN NEW;
                END IF;
                pt := geometry_period_point(COALESCE(NEW.geom, NEW.territory_geom));
                IF pt IS NULL THEN
                    RETURN NEW;
                END IF;

                UPDATE entity_locations
                SET geom = pt, location_method = COALESCE(location_method, 'geometry_period'), updated_at = now()
                WHERE entity_id = NEW.entity_id AND is_primary = true;
                -- No primary row yet: none is added here. Writers that add the
                -- period first and the location after would hit the one-primary rule.

                RETURN NEW;
            END $$;

            DROP TRIGGER IF EXISTS geometry_periods_set_primary_point ON geometry_periods;
            CREATE TRIGGER geometry_periods_set_primary_point
                AFTER INSERT OR UPDATE OF geom, territory_geom, provenance_mode ON geometry_periods
                FOR EACH ROW EXECUTE FUNCTION set_primary_point_from_geometry_period();
            SQL);

        // The rows that exist already: the newest own period of each unplaced entity.
        $source = <<<'SQL'
            SELECT DISTINCT ON (gp.entity_id) gp.entity_id,
                geometry_period_point(COALESCE(gp.geom, gp.territory_geom)) AS pt
            FROM geometry_periods gp
            WHERE gp.provenance_mode <> 'derived'
              AND NOT EXISTS (
                  SELECT 1 FROM entity_locations el
                  WHERE el.entity_id = gp.entity_id AND el.is_primary = true AND el.geom IS NOT NULL
              )
            ORDER BY gp.entity_id, gp.start_year DESC NULLS LAST
            SQL;

        DB::statement(
            <<<SQL
            UPDATE entity_locations el
            SET geom = src.pt, location_method = COALESCE(el.location_method, 'geometry_period'), updated_at = now()
            FROM ({$source}) src
            WHERE el.entity_id = src.entity_id AND el.is_primary = true AND src.pt IS NOT NULL
            SQL
        );

        DB::statement(
            <<<SQL
            INSERT INTO entity_locations (location_id, entity_id, geom, location_method, is_primary, created_at, updated_at)
            SELECT gen_random_uuid(), src.entity_id, src.pt, 'geometry_period', true, now(), now()
            FROM ({$source}) src
            WHERE src.pt IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM entity_locations el WHERE el.entity_id = src.entity_id AND el.is_primary = true)
            SQL
        );
    }

    public function down(): void
    {
        DB::unprepared(<<<'SQL'
            DROP TRIGGER IF EXISTS geometry_periods_set_primary_point ON geometry_periods;
            DROP FUNCTION IF EXISTS set_primary_point_from_geometry_period();
            DROP FUNCTION IF EXISTS geometry_period_point(geometry);
            SQL);
        // The points already set stay.
    }
};
