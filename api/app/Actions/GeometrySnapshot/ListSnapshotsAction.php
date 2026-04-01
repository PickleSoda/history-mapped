<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Support\Collection;

/**
 * List all geometry snapshots for an entity, ordered chronologically.
 * Returns GeoJSON-ready serialisable data via ST_AsGeoJSON inline select.
 *
 * @return Collection<int, GeometrySnapshot>
 */
class ListSnapshotsAction
{
    /** @return Collection<int, GeometrySnapshot> */
    public function __invoke(Entity $entity): Collection
    {
        return GeometrySnapshot::query()
            ->forEntity($entity->entity_id)
            ->with('geoRef')
            ->withGeoJson()
            ->orderChronologically()
            ->get();
    }
}
