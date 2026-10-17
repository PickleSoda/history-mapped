<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Actions\Tag\SyncTagsAction;
use App\DTOs\EntityData;
use App\Enums\TagSource;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTemporalRange;
use Illuminate\Support\Facades\DB;

/**
 * Update an existing Entity.
 *
 * Supports partial updates — only fields present in the DTO are applied.
 * Geometry columns handled via raw PostGIS SQL.
 */
class UpdateEntityAction
{
    /**
     * Attribute keys owned by the image fetcher and the admin Images panel. A
     * write whose attributes omit them keeps the stored values, so a form save
     * or a pipeline re-import doesn't drop linked images.
     *
     * @var list<string>
     */
    private const PRESERVED_ATTRIBUTES = ['media_refs', FetchEntityImagesAction::CURATED_KEY];

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

            if (is_array($modelData['attributes'] ?? null)) {
                foreach (self::PRESERVED_ATTRIBUTES as $key) {
                    if (! array_key_exists($key, $modelData['attributes']) && isset($entity->attributes[$key])) {
                        $modelData['attributes'][$key] = $entity->attributes[$key];
                    }
                }
            }

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
            app(SyncTagsAction::class)($entity, $data->tags, TagSource::Manual);
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
