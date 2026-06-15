<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefProvider;
use App\Models\Entity;
use App\Models\EntityGeoRef;

class AttachOhmGeoRefAction
{
    public function __construct(
        private readonly CreateEntityGeoRefAction $createEntityGeoRef,
        private readonly HydrateEntityGeometryFromGeoRefAction $hydrateGeometry,
        private readonly PrepareGeoRefAttachmentAction $prepareGeoRefAttachment,
    ) {}

    /**
     * @param  array<string, mixed>  $attributes
     */
    public function __invoke(Entity $entity, array $attributes): EntityGeoRef
    {
        $prepared = (($attributes['provider'] ?? null) === GeoRefProvider::Ohm->value)
            ? $this->prepareGeoRefAttachment->__invoke($attributes)
            : ['attributes' => $attributes, 'geojson' => null];

        $geoRef = $this->createEntityGeoRef->__invoke($entity, $prepared['attributes']);

        if (is_array($prepared['geojson'])) {
            $this->hydrateGeometry->__invoke($entity, $geoRef, $prepared['geojson']);
        }

        return $geoRef->fresh();
    }
}
