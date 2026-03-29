<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Models\EntityGeoRef;
use Illuminate\Support\Facades\DB;

class DeleteEntityGeoRefAction
{
    public function __invoke(EntityGeoRef $geoRef): void
    {
        DB::transaction(function () use ($geoRef): void {
            $entity = $geoRef->entity;

            if ($entity !== null && $entity->primary_geo_ref_id === $geoRef->geo_ref_id) {
                $entity->forceFill([
                    'primary_geo_ref_id' => null,
                ])->save();
            }

            $geoRef->delete();
        });
    }
}
