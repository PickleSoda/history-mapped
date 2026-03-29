<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefMatchRole;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class CreateEntityGeoRefAction
{
    /**
     * @param  array<string, mixed>  $attributes
     */
    public function __invoke(Entity $entity, array $attributes): EntityGeoRef
    {
        return DB::transaction(function () use ($entity, $attributes): EntityGeoRef {
            $isActive = (bool) ($attributes['is_active'] ?? true);
            $isPrimary = ($attributes['match_role'] ?? null) === GeoRefMatchRole::Primary->value;

            if ($isPrimary && $isActive) {
                EntityGeoRef::query()
                    ->where('entity_id', $entity->entity_id)
                    ->where('match_role', GeoRefMatchRole::Primary->value)
                    ->where('is_active', true)
                    ->update([
                        'is_active' => false,
                        'updated_at' => now(),
                    ]);
            }

            $geoRef = new EntityGeoRef([
                ...$attributes,
                'geo_ref_id' => $attributes['geo_ref_id'] ?? Str::uuid()->toString(),
                'entity_id' => $entity->entity_id,
                'is_active' => $isActive,
            ]);

            $geoRef->save();

            if ($isPrimary && $isActive) {
                $entity->forceFill([
                    'primary_geo_ref_id' => $geoRef->geo_ref_id,
                ])->save();
            }

            return $geoRef->fresh();
        });
    }
}
