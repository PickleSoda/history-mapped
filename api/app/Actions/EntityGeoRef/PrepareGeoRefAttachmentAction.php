<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefProvider;
use App\Services\Ohm\OhmLookupService;

class PrepareGeoRefAttachmentAction
{
    public function __construct(
        private readonly OhmLookupService $lookupService,
    ) {}

    /**
     * @param  array<string, mixed>  $attributes
     * @return array{attributes: array<string, mixed>, geojson: array<string, mixed>|null}
     */
    public function __invoke(array $attributes): array
    {
        $lookup = null;

        if (($attributes['provider'] ?? null) === GeoRefProvider::Ohm->value) {
            $lookup = $this->lookupService->lookupByIdentity(
                (string) $attributes['external_type'],
                (string) $attributes['external_id'],
            );

            if (is_array($lookup)) {
                $attributes['external_tags'] = $attributes['external_tags'] ?? $lookup['external_tags'] ?? null;
                $attributes['source_meta'] = array_merge(
                    is_array($lookup['source_meta'] ?? null) ? $lookup['source_meta'] : [],
                    is_array($attributes['source_meta'] ?? null) ? $attributes['source_meta'] : [],
                );
                $attributes['external_type'] = $lookup['external_type'] ?? $attributes['external_type'];
                $attributes['external_id'] = $lookup['external_id'] ?? $attributes['external_id'];
            }
        }

        return [
            'attributes' => $attributes,
            'geojson' => is_array($lookup['geojson'] ?? null) ? $lookup['geojson'] : null,
        ];
    }
}
