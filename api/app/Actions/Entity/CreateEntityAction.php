<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\DTOs\EntityData;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTag;
use App\Models\EntityTemporalRange;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Create a new Entity with optional PostGIS geometry.
 *
 * Wraps the insert in a transaction because geometry columns
 * require raw SQL (ST_GeomFromGeoJSON) alongside Eloquent fill.
 */
class CreateEntityAction
{
    /** @var list<string> */
    private const LEGACY_ENTITY_COLUMNS = [
        'tags',
        'alternative_names',
        'temporal_start',
        'temporal_end',
        'temporal_start_year',
        'temporal_end_year',
        'location_name',
    ];

    public function __invoke(EntityData $data, ?string $createdBy = null): Entity
    {
        return DB::transaction(function () use ($data, $createdBy): Entity {
            $modelData = $data->toModelArray();

            foreach (self::LEGACY_ENTITY_COLUMNS as $column) {
                unset($modelData[$column]);
            }

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

            // Generate UUID in PHP so Eloquent knows the primary key after insert
            $modelData['entity_id'] = Str::uuid()->toString();

            $entity = Entity::create($modelData);

            $this->syncCanonicalRelations($entity, $data, $geojson, $territoryGeojson);

            return $entity->fresh();
        });
    }

    /**
     * @param  array<string, mixed>|null  $geojson
     * @param  array<string, mixed>|null  $territoryGeojson
     */
    private function syncCanonicalRelations(Entity $entity, EntityData $data, ?array $geojson, ?array $territoryGeojson): void
    {
        if (is_array($data->alternativeNames)) {
            foreach ($data->alternativeNames as $alias) {
                if (! is_string($alias) || trim($alias) === '') {
                    continue;
                }

                EntityAlias::query()->firstOrCreate([
                    'entity_id' => $entity->entity_id,
                    'name' => trim($alias),
                ], [
                    'is_primary' => false,
                ]);
            }
        }

        if (is_array($data->tags)) {
            foreach ($data->tags as $tag) {
                if (! is_string($tag) || trim($tag) === '') {
                    continue;
                }

                EntityTag::query()->firstOrCreate([
                    'entity_id' => $entity->entity_id,
                    'tag' => trim($tag),
                ]);
            }
        }

        if ($data->temporalStart !== null || $data->temporalEnd !== null) {
            EntityTemporalRange::query()->updateOrCreate(
                [
                    'entity_id' => $entity->entity_id,
                    'is_primary' => true,
                ],
                [
                    'range_type' => 'primary',
                    'start_date' => $data->temporalStart,
                    'end_date' => $data->temporalEnd,
                    'duration_type' => $data->durationType,
                    'date_method' => $data->dateMethod,
                    'date_confidence' => $data->dateConfidence,
                ],
            );
        }

        if ($data->locationName !== null || $geojson !== null || $territoryGeojson !== null) {
            EntityLocation::query()->updateOrCreate(
                [
                    'entity_id' => $entity->entity_id,
                    'is_primary' => true,
                ],
                [
                    'location_name' => $data->locationName,
                    'geom' => $geojson,
                    'territory_geom' => $territoryGeojson,
                    'location_method' => $data->locationMethod,
                    'location_confidence' => $data->locationConfidence,
                ],
            );
        }
    }
}
