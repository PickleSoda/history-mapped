<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityLocation;

class BackfillLocationsAction
{
    public function __invoke(Entity $entity): int
    {
        if ($entity->location_name === null && $entity->geom === null && $entity->territory_geom === null) {
            return 0;
        }

        EntityLocation::query()
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => $entity->location_name,
            'location_method' => $entity->location_method?->value,
            'location_confidence' => $entity->location_confidence?->value,
            'is_primary' => true,
            'geom' => $entity->geom,
            'territory_geom' => $entity->territory_geom,
        ]);

        return 1;
    }
}
