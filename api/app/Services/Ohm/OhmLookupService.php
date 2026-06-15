<?php

declare(strict_types=1);

namespace App\Services\Ohm;

use App\Enums\GeoRefExternalType;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Http;

class OhmLookupService
{
    /**
     * @return array<string, mixed>|null
     */
    public function lookupByIdentity(string $externalType, string $externalId): ?array
    {
        $osmType = $this->toLookupPrefix($externalType);

        $response = Http::baseUrl((string) config('services.ohm.nominatim_base_url'))
            ->timeout((int) config('services.ohm.timeout', 20))
            ->get('/lookup', [
                'format' => 'jsonv2',
                'polygon_geojson' => 1,
                'extratags' => 1,
                'osm_ids' => $osmType.$externalId,
            ]);

        if (! $response->successful()) {
            return null;
        }

        $items = $response->json();
        if (! is_array($items) || $items === []) {
            return null;
        }

        $first = $items[0] ?? null;

        return is_array($first) ? $this->normalizeLookupResult($first) : null;
    }

    /**
     * @return list<array<string, mixed>>
     */
    public function searchByName(string $name, ?string $locationName = null): array
    {
        $query = trim($locationName !== null && $locationName !== '' ? $name.' '.$locationName : $name);

        $response = Http::baseUrl((string) config('services.ohm.nominatim_base_url'))
            ->timeout((int) config('services.ohm.timeout', 20))
            ->get('/search', [
                'q' => $query,
                'format' => 'jsonv2',
                'limit' => 5,
                'polygon_geojson' => 1,
                'extratags' => 1,
            ]);

        if (! $response->successful()) {
            return [];
        }

        $items = $response->json();
        if (! is_array($items) || $items === []) {
            return [];
        }

        return array_values(array_filter(array_map(
            fn (mixed $item): ?array => is_array($item) ? $this->normalizeLookupResult($item) : null,
            $items,
        )));
    }

    private function toLookupPrefix(string $externalType): string
    {
        return match ($externalType) {
            GeoRefExternalType::Node->value => 'N',
            GeoRefExternalType::Way->value => 'W',
            GeoRefExternalType::Relation->value => 'R',
            default => 'R',
        };
    }

    private function toExternalType(mixed $osmType): string
    {
        $type = is_string($osmType) ? strtolower($osmType) : '';

        return match ($type) {
            'n', 'node' => GeoRefExternalType::Node->value,
            'w', 'way' => GeoRefExternalType::Way->value,
            'r', 'relation' => GeoRefExternalType::Relation->value,
            default => GeoRefExternalType::Feature->value,
        };
    }

    /**
     * @param  array<string, mixed>  $item
     * @return array<string, mixed>
     */
    private function normalizeLookupResult(array $item): array
    {
        return [
            'external_type' => $this->toExternalType($item['osm_type'] ?? null),
            'external_id' => (string) ($item['osm_id'] ?? ''),
            'display_name' => $item['display_name'] ?? null,
            'match_label' => $this->extractMatchLabel($item),
            'geojson' => is_array($item['geojson'] ?? null) ? $item['geojson'] : null,
            'external_tags' => is_array($item['extratags'] ?? null) ? $item['extratags'] : [],
            'source_meta' => [
                'display_name' => $item['display_name'] ?? null,
                'class' => $item['class'] ?? null,
                'type' => $item['type'] ?? null,
                'lat' => Arr::get($item, 'lat'),
                'lon' => Arr::get($item, 'lon'),
                'raw' => $item,
            ],
        ];
    }

    /**
     * @param  array<string, mixed>  $item
     */
    private function extractMatchLabel(array $item): ?string
    {
        $name = $item['extratags']['name'] ?? null;
        if (is_string($name) && $name !== '') {
            return $name;
        }

        $displayName = $item['display_name'] ?? null;
        if (! is_string($displayName) || $displayName === '') {
            return null;
        }

        $segments = preg_split('/\s*,\s*/', $displayName);
        $label = is_array($segments) ? ($segments[0] ?? null) : null;

        return is_string($label) && $label !== '' ? $label : $displayName;
    }
}
