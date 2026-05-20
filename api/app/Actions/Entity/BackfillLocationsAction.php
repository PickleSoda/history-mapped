<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use App\Models\EntityLocation;

class BackfillLocationsAction
{
    public function __invoke(Entity $entity): int
    {
        $location = $entity->primaryLocation;

        if ($location === null) {
            return 0;
        }

        EntityLocation::query()
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => $location->location_name,
            'location_method' => $location->location_method,
            'location_confidence' => $location->location_confidence,
            'is_primary' => true,
            'geom' => $location->geom,
            'territory_geom' => $location->territory_geom,
        ]);

        return 1;
    }
}
