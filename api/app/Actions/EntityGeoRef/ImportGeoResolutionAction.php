<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Support\Facades\Log;

/**
 * Import a geo-resolution manifest produced by the Python pipeline.
 *
 * Reads the `_geo_resolution` key from a JSONL record and, when the
 * pipeline reports a match, persists it via CreateEntityGeoRefAction
 * and optionally hydrates the entity geometry.
 */
class ImportGeoResolutionAction
{
    private const RESOLVER_TO_LOCATION_METHOD = [
        'ohm_nominatim' => 'ohm_nominatim',
        'wikidata_coords' => 'wikidata',
    ];

    public function __construct(
        private readonly CreateEntityGeoRefAction $createGeoRef,
        private readonly HydrateEntityGeometryFromGeoRefAction $hydrateGeometry,
    ) {}

    /**
     * @param  array<string, mixed>|null  $manifest  — The `_geo_resolution` value from the JSONL record.
     */
    public function __invoke(Entity $entity, ?array $manifest): ?EntityGeoRef
    {
        if ($manifest === null || ($manifest['status'] ?? null) !== 'matched') {
            return null;
        }

        // Don't overwrite existing geo-refs
        if ($entity->primary_geo_ref_id !== null || $entity->geoRefs()->exists()) {
            return null;
        }

        $geoRefData = $manifest['geo_ref'] ?? null;
        if (! is_array($geoRefData) || empty($geoRefData['external_id'])) {
            Log::warning('[Pipeline] _geo_resolution matched but geo_ref missing or invalid', [
                'entity_id' => $entity->entity_id,
            ]);

            return null;
        }

        // Validate enum values before persisting
        $provider = GeoRefProvider::tryFrom($geoRefData['provider'] ?? '');
        $externalType = GeoRefExternalType::tryFrom($geoRefData['external_type'] ?? '');
        $matchRole = GeoRefMatchRole::tryFrom($geoRefData['match_role'] ?? '');
        $retrievalMethod = GeoRefRetrievalMethod::tryFrom($geoRefData['retrieval_method'] ?? '');

        if (! $provider || ! $externalType || ! $matchRole || ! $retrievalMethod) {
            Log::warning('[Pipeline] _geo_resolution contains invalid enum values', [
                'entity_id' => $entity->entity_id,
                'geo_ref' => $geoRefData,
            ]);

            return null;
        }

        $geoRef = $this->createGeoRef->__invoke($entity, [
            'provider' => $provider->value,
            'external_type' => $externalType->value,
            'external_id' => (string) $geoRefData['external_id'],
            'match_role' => $matchRole->value,
            'retrieval_method' => $retrievalMethod->value,
            'match_score' => (float) ($geoRefData['match_score'] ?? 0.0),
            'external_tags' => $geoRefData['external_tags'] ?? null,
            'source_meta' => $geoRefData['source_meta'] ?? null,
            'is_active' => true,
        ]);

        // Hydrate geometry if the pipeline included it
        $geometry = $manifest['geometry'] ?? null;
        if (is_array($geometry)) {
            $resolver = $manifest['provenance']['resolver'] ?? 'ohm_nominatim';
            $this->hydrateGeometry->__invoke($entity, $geoRef, $geometry, self::RESOLVER_TO_LOCATION_METHOD[$resolver] ?? 'ohm_nominatim');
        }

        return $geoRef->fresh();
    }
}
