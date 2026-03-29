<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Services\Ohm\OhmLookupService;

class AutoAttachOhmGeoRefAction
{
    public function __construct(
        private readonly CreateEntityGeoRefAction $createEntityGeoRef,
        private readonly HydrateEntityGeometryFromGeoRefAction $hydrateGeometry,
        private readonly OhmLookupService $lookupService,
    ) {}

    public function __invoke(Entity $entity): ?EntityGeoRef
    {
        if ($entity->primary_geo_ref_id !== null || $entity->geoRefs()->exists()) {
            return null;
        }

        $match = $this->selectBestMatch(
            $entity->name,
            $this->lookupService->searchByName($entity->name, $entity->location_name),
        );

        if (! is_array($match) || ($match['external_id'] ?? null) === null) {
            return null;
        }

        $score = $this->determineMatchScore($entity->name, $match['match_label'] ?? $match['display_name'] ?? null);

        $geoRef = $this->createEntityGeoRef->__invoke($entity, [
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => $match['external_type'],
            'external_id' => $match['external_id'],
            'match_role' => GeoRefMatchRole::Primary->value,
            'retrieval_method' => GeoRefRetrievalMethod::Nominatim->value,
            'external_tags' => $match['external_tags'] ?? null,
            'source_meta' => $match['source_meta'] ?? null,
            'match_score' => $score,
            'is_active' => true,
        ]);

        if (is_array($match['geojson'] ?? null)) {
            $this->hydrateGeometry->__invoke($entity, $geoRef, $match['geojson']);
        }

        return $geoRef->fresh();
    }

    private function determineMatchScore(string $entityName, mixed $displayName): float
    {
        return $this->normalizeName($entityName) === $this->normalizeName(is_string($displayName) ? $displayName : '')
            ? 1.0
            : 0.0;
    }

    /**
     * @param  list<array<string, mixed>>  $matches
     * @return array<string, mixed>|null
     */
    private function selectBestMatch(string $entityName, array $matches): ?array
    {
        $normalizedName = $this->normalizeName($entityName);

        foreach ($matches as $match) {
            $label = $match['match_label'] ?? $match['display_name'] ?? null;
            if ($this->normalizeName(is_string($label) ? $label : '') === $normalizedName) {
                return $match;
            }
        }

        return null;
    }

    private function normalizeName(string $value): string
    {
        $normalized = strtolower(trim($value));
        $normalized = preg_replace('/[^a-z0-9]+/', ' ', $normalized) ?? $normalized;

        return trim($normalized);
    }
}