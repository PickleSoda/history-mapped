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
    public function __invoke(Entity $entity, EntityGeoRef $geoRef, ?array $geojson, string $locationMethod = 'ohm_nominatim'): Entity
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
                sprintf('UPDATE entities SET %s = ST_SetSRID(ST_GeomFromGeoJSON(?), 4326) WHERE entity_id = ?', $column),
                [json_encode($normalized), $currentEntity->entity_id],
            );

            if ($currentEntity->primary_geo_ref_id === $geoRef->geo_ref_id) {
                DB::statement(
                    'UPDATE entities SET location_method = ?::location_resolution_method WHERE entity_id = ?',
                    [$locationMethod, $currentEntity->entity_id],
                );
            }
        });

        return $entity->fresh();
    }
}