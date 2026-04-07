<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\DTOs\EntityData;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTag;
use App\Models\EntityTemporalRange;
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
        'tags',
        'alternative_names',
        'temporal_start',
        'temporal_end',
        'temporal_start_year',
        'temporal_end_year',
        'location_name',
    ];

    public function __invoke(Entity $entity, EntityData $data): Entity
    {
        return DB::transaction(function () use ($entity, $data): Entity {
            $modelData = $data->toModelArray();

            foreach (self::LEGACY_ENTITY_COLUMNS as $column) {
                unset($modelData[$column]);
            }

            // Extract geometry — handled separately
            $geojson = $data->geojson;
            $territoryGeojson = $data->territoryGeojson;
            unset($modelData['geojson'], $modelData['territory_geojson']);

            $entity->update($modelData);

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
            EntityAlias::query()->where('entity_id', $entity->entity_id)->delete();

            foreach ($data->alternativeNames as $alias) {
                if (! is_string($alias) || trim($alias) === '') {
                    continue;
                }

                EntityAlias::query()->create([
                    'entity_id' => $entity->entity_id,
                    'name' => trim($alias),
                    'is_primary' => false,
                ]);
            }
        }

        if (is_array($data->tags)) {
            EntityTag::query()->where('entity_id', $entity->entity_id)->delete();

            foreach (array_unique($data->tags) as $tag) {
                if (! is_string($tag) || trim($tag) === '') {
                    continue;
                }

                EntityTag::query()->create([
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
                    'start_year' => $data->temporalStart !== null ? self::extractYear($data->temporalStart) : null,
                    'end_year' => $data->temporalEnd !== null ? self::extractYear($data->temporalEnd) : null,
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

    private static function extractYear(string $value): ?int
    {
        if (preg_match('/^-?\d+/', trim($value), $matches) !== 1) {
            return null;
        }

        return (int) $matches[0];
    }
}
