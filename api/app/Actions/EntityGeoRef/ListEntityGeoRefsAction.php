<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Database\Eloquent\Collection;

class ListEntityGeoRefsAction
{
    /**
     * @return Collection<int, EntityGeoRef>
     */
    public function __invoke(Entity $entity): Collection
    {
        return $entity->geoRefs()->get();
    }
}
