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
    /** @var list<string> */
    private const LEGACY_ENTITY_COLUMNS = [
        'temporal_start',
        'temporal_end',
        'temporal_start_year',
        'temporal_end_year',
        'location_name',
        'location_confidence',
        'location_method',
    ];

    public function __invoke(Entity $entity, EntityData $data): Entity
    {
        return DB::transaction(function () use ($entity, $data): Entity {
            $modelData = $data->toModelArray();
            $v2WritesEnabled = (bool) config('entity_model.entity_model_v2_write_enabled', false);

            if ($v2WritesEnabled) {
                foreach (self::LEGACY_ENTITY_COLUMNS as $column) {
                    unset($modelData[$column]);
                }
            }

            // Extract geometry — handled separately
            $geojson = $data->geojson;
            $territoryGeojson = $data->territoryGeojson;
            unset($modelData['geojson'], $modelData['territory_geojson']);

            $entity->update($modelData);

            // Update geometry columns via PostGIS
            if (! $v2WritesEnabled && $geojson !== null) {
                DB::statement(
                    'UPDATE entities SET geom = ST_GeomFromGeoJSON(?) WHERE entity_id = ?',
                    [json_encode($geojson), $entity->entity_id],
                );
            }

            if (! $v2WritesEnabled && $territoryGeojson !== null) {
                DB::statement(
                    'UPDATE entities SET territory_geom = ST_GeomFromGeoJSON(?) WHERE entity_id = ?',
                    [json_encode($territoryGeojson), $entity->entity_id],
                );
            }

            return $entity->fresh();
        });
    }
}
