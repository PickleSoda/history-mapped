<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;

/**
 * Retrieve a single entity by ID with optional eager-loaded relationships.
 */
class GetEntityAction
{
    /**
     * @param  list<string>  $with  Relations to eager-load
     */
    public function __invoke(string $entityId, array $with = []): Entity
    {
        $query = Entity::query()
            ->where('entity_id', $entityId)
            ->withCount('geometrySnapshots');

        if ($with !== []) {
            $query->with($with);
        }

        return $query->firstOrFail();
    }
}
