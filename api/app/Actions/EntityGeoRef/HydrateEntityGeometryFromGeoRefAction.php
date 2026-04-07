<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Support\Geometry\NormalizeGeoJsonForPostgis;
use Illuminate\Support\Facades\DB;

class HydrateEntityGeometryFromGeoRefAction
{
    /**
     * @param  array<string, mixed>|null  $geojson
     */
    public function __invoke(Entity $entity, EntityGeoRef $geoRef, ?array $geojson, ?string $locationMethod = 'ohm_nominatim'): Entity
    {
        $normalized = NormalizeGeoJsonForPostgis::normalize($geojson);

        if ($normalized === null) {
            return $entity;
        }

        $type = $normalized['type'] ?? null;
        $column = in_array($type, ['Polygon', 'MultiPolygon'], true)
            ? 'territory_geom'
            : 'geom';
        $currentEntity = $entity->fresh();

        DB::transaction(function () use ($currentEntity, $geoRef, $normalized, $column, $locationMethod): void {
            DB::statement(
                sprintf(
                    "UPDATE entity_locations
                     SET %s = ST_SetSRID(ST_GeomFromGeoJSON(?), 4326),
                                                 location_method = COALESCE(location_method, ?),
                         updated_at = NOW()
                     WHERE entity_id = ?
                       AND is_primary = true",
                    $column,
                ),
                [json_encode($normalized), $locationMethod, $currentEntity->entity_id],
            );

            DB::statement(
                sprintf(
                    "INSERT INTO entity_locations (
                        location_id, entity_id, location_name, %s,
                        location_method, location_confidence, is_primary,
                        created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(), ?, NULL,
                        ST_SetSRID(ST_GeomFromGeoJSON(?), 4326),
                        ?, NULL, true,
                        NOW(), NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM entity_locations
                        WHERE entity_id = ? AND is_primary = true
                    )",
                    $column,
                ),
                [
                    $currentEntity->entity_id,
                    json_encode($normalized),
                    $locationMethod,
                    $currentEntity->entity_id,
                ],
            );

            if ($currentEntity->primary_geo_ref_id === $geoRef->geo_ref_id && $locationMethod !== null) {
                DB::statement(
                    'UPDATE entities SET location_method = ?::location_resolution_method WHERE entity_id = ?',
                    [$locationMethod, $currentEntity->entity_id],
                );
            }
        });

        return $entity->fresh();
    }
}