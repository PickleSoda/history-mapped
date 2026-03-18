<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\DTOs\EntityData;
use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Create a new Entity with optional PostGIS geometry.
 *
 * Wraps the insert in a transaction because geometry columns
 * require raw SQL (ST_GeomFromGeoJSON) alongside Eloquent fill.
 */
class CreateEntityAction
{
    public function __invoke(EntityData $data, ?string $createdBy = null): Entity
    {
        return DB::transaction(function () use ($data, $createdBy): Entity {
            $modelData = $data->toModelArray();

            if ($createdBy !== null) {
                $modelData['created_by'] = $createdBy;
            }

            // Default verification status for new entities
            if (! isset($modelData['verification_status'])) {
                $modelData['verification_status'] = 'pipeline_draft';
            }

            // Extract geometry data — handled via raw SQL, not Eloquent cast
            $geojson = $data->geojson;
            $territoryGeojson = $data->territoryGeojson;
            unset($modelData['geojson'], $modelData['territory_geojson']);

            $entity = Entity::create($modelData);

            // Set geometry columns via PostGIS functions
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
