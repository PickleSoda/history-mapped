<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Models\Entity;
use App\Models\EntityGeoRef;

class PruneOrphanGeometryPeriodGeoRefAction
{
    /**
     * Remove inactive geometry-period scoped geo refs that are not primary.
     *
     * @return int Number of deleted rows.
     */
    public function __invoke(Entity $entity): int
    {
        $query = EntityGeoRef::query()
            ->where('entity_id', $entity->entity_id)
            ->where('is_active', false)
            ->whereRaw("COALESCE(source_meta->>'origin', '') = 'geometry_period'");

        if ($entity->primary_geo_ref_id !== null) {
            $query->where('geo_ref_id', '!=', $entity->primary_geo_ref_id);
        }

        return $query->delete();
    }
}
