<?php

namespace App\Ai\Tools\Concerns;

use App\Services\Geo\PlaceFinder;
use Laravel\Ai\Tools\Request;
use LogicException;

/**
 * Shared plumbing for the read-only placement tools (point_from_offset,
 * point_between, nearest_coast, find_place): reading an anchor given either as
 * lon/lat or as an entity, and a uniform result a small model can chain or
 * hand straight to set_entity_location. The using tool injects a PlaceFinder
 * as `$places`.
 */
trait ComputesPlacement
{
    /**
     * The anchor named by `{$prefix}lon` + `{$prefix}lat`, or else by
     * `{$prefix}entity_id` (a UUID or an exact name).
     *
     * @return array{lon: float, lat: float, label: string, warning?: string}|array{error: string}
     */
    protected function anchor(Request $request, string $prefix, string $role): array
    {
        $lon = $request[$prefix.'lon'] ?? null;
        $lat = $request[$prefix.'lat'] ?? null;
        $ref = $request[$prefix.'entity_id'] ?? null;

        if (is_numeric($lon) && is_numeric($lat)) {
            if (abs((float) $lat) > 90 || abs((float) $lon) > 180) {
                return ['error' => "{$role} is out of range: lon must be -180..180 and lat -90..90 (lon is east-west)."];
            }

            return ['lon' => (float) $lon, 'lat' => (float) $lat, 'label' => self::coords((float) $lon, (float) $lat)];
        }

        if (is_string($ref) && trim($ref) !== '') {
            $point = $this->places->entityPoint(trim($ref));
            if (isset($point['error'])) {
                return ['error' => $point['error']];
            }

            return array_filter([
                'lon' => $point['lon'],
                'lat' => $point['lat'],
                'label' => $point['name'].' '.self::coords($point['lon'], $point['lat']),
                'warning' => isset($point['note']) ? "{$point['name']}: {$point['note']}" : null,
            ], fn ($v) => $v !== null);
        }

        return ['error' => "Give {$role} as {$prefix}lon + {$prefix}lat, or as {$prefix}entity_id. Use find_place to look a name up first."];
    }

    /**
     * A placement result: the point, any extra facts, a one-line explanation
     * and what to do next.
     *
     * @param  array<string, mixed>  $extra
     * @param  list<string>  $warnings
     */
    protected function placed(float $lon, float $lat, string $explanation, array $extra = [], array $warnings = []): string
    {
        return json_encode(array_filter([
            'lon' => round($lon, 5),
            'lat' => round($lat, 5),
            ...$extra,
            'explanation' => $explanation,
            'warnings' => $warnings !== [] ? array_values($warnings) : null,
            'next' => 'Pass lon and lat to set_entity_location with a short location_name (e.g. "20 km north of Rome"). Or chain: use this lon/lat as the anchor of another placement tool.',
        ], fn ($v) => $v !== null), JSON_THROW_ON_ERROR);
    }

    protected function failure(string $message): string
    {
        return json_encode(['error' => $message], JSON_THROW_ON_ERROR);
    }

    protected static function coords(float $lon, float $lat): string
    {
        return sprintf('(%.5f, %.5f)', $lon, $lat);
    }

    public function buildParts(array $args): array
    {
        throw new LogicException(static::name().' is a read-only tool — it does not stage proposals.');
    }

    public function applyPart(array $payload, array $resolved): array
    {
        throw new LogicException(static::name().' is a read-only tool — it does not apply parts.');
    }
}
