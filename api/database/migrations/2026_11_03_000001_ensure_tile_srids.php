<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Guarantee the two spatial-reference rows the atlas tiles depend on.
 *
 * `tiles.atlas_entities` (served by Martin or by the app tile driver) calls
 * ST_Transform between EPSG:4326 and EPSG:3857 on every request, and
 * ST_Transform reads its projection strings from `spatial_ref_sys`. PostGIS
 * fills that table on CREATE EXTENSION, but the production database was found
 * without the rows on 2026-11-03 ("Cannot find SRID (3857) in spatial_ref_sys"
 * on every tile; nothing else in the app transforms geometries, so nothing
 * else noticed). The rows below are verbatim from PostGIS 3.5's
 * spatial_ref_sys.sql; ON CONFLICT DO NOTHING leaves a healthy table alone.
 * A full reload is `psql -f /usr/share/postgresql/16/contrib/postgis-3.5/spatial_ref_sys.sql`
 * in the db container (docs/implementation-docs/content-data-transfer.md, Gotchas).
 */
return new class extends Migration
{
    /** srid => [auth_name, auth_srid, srtext, proj4text] */
    private const ROWS = [
        3857 => ['EPSG', 3857, 'PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],EXTENSION["PROJ4","+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs"],AUTHORITY["EPSG","3857"]]', '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs'],
        4326 => ['EPSG', 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]', '+proj=longlat +datum=WGS84 +no_defs '],
    ];

    public function up(): void
    {
        foreach (self::ROWS as $srid => [$authName, $authSrid, $srtext, $proj4text]) {
            DB::insert(
                'INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
                 VALUES (?, ?, ?, ?, ?) ON CONFLICT (srid) DO NOTHING',
                [$srid, $authName, $authSrid, $srtext, $proj4text],
            );
        }
    }

    /** Reference data that PostGIS itself ships: nothing to undo. */
    public function down(): void {}
};
