<?php

declare(strict_types=1);

namespace App\Casts;

use Illuminate\Contracts\Database\Eloquent\CastsAttributes;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\DB;

/**
 * Cast a PostGIS geometry column to/from a GeoJSON array.
 *
 * get(): WKB hex (from PostGIS) -> GeoJSON associative array
 * set(): GeoJSON array/string   -> DB expression via ST_GeomFromGeoJSON
 */
class GeoJson implements CastsAttributes
{
    /**
     * Convert the raw PostGIS WKB hex value to a GeoJSON array.
     *
     * @param  Model  $model
     * @param  string  $key
     * @param  mixed  $value
     * @param  array<string, mixed>  $attributes
     * @return array<string, mixed>|null
     */
    public function get(Model $model, string $key, mixed $value, array $attributes): ?array
    {
        if ($value === null) {
            return null;
        }

        $result = DB::selectOne(
            'SELECT ST_AsGeoJSON(?) AS geojson',
            [$value],
        );

        if ($result === null || $result->geojson === null) {
            return null;
        }

        return json_decode($result->geojson, true);
    }

    /**
     * Convert a GeoJSON array or string to a PostGIS geometry expression.
     *
     * Uses ST_SetSRID(ST_GeomFromGeoJSON(...), 4326) so the SRID is always
     * set correctly at input time (per PostGIS best practices).
     *
     * @param  Model  $model
     * @param  string  $key
     * @param  mixed  $value
     * @param  array<string, mixed>  $attributes
     * @return \Illuminate\Database\Query\Expression|null
     */
    public function set(Model $model, string $key, mixed $value, array $attributes): mixed
    {
        if ($value === null) {
            return null;
        }

        $json = is_array($value) ? json_encode($value) : $value;

        // Escape single quotes in the JSON string for the raw SQL expression.
        $escaped = str_replace("'", "''", $json);

        return DB::raw("ST_SetSRID(ST_GeomFromGeoJSON('{$escaped}'), 4326)");
    }
}
