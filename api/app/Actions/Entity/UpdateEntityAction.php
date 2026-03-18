<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\DTOs\EntityData;
use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Update an existing Entity.
 *
 * Supports partial updates — only fields present in the DTO are applied.
 * Geometry columns handled via raw PostGIS SQL.
 */
class UpdateEntityAction
{
    public function __invoke(Entity $entity, EntityData $data): Entity
    {
        return DB::transaction(function () use ($entity, $data): Entity {
            $modelData = $data->toModelArray();

            // Extract geometry — handled separately
            $geojson = $data->geojson;
            $territoryGeojson = $data->territoryGeojson;
            unset($modelData['geojson'], $modelData['territory_geojson']);

            $entity->update($modelData);

            // Update geometry columns via PostGIS
            if ($geojson !== null) {
                DB::statement(
                    'UPDATE entities SET geom = ST_GeomFromGeoJSON(?) WHERE entity_id = ?',
                    [json_encode($geojson), $entity->entity_id],
                );
            }

            if ($territoryGeojson !== null) {
                DB::statement(
                    'UPDATE entities SET territory_geom = ST_GeomFromGeoJSON(?) WHERE entity_id = ?',
                    [json_encode($territoryGeojson), $entity->entity_id],
                );
            }

            return $entity->fresh();
        });
    }
}
