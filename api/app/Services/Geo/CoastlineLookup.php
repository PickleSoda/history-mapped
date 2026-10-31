<?php

declare(strict_types=1);

namespace App\Services\Geo;

use Illuminate\Support\Facades\Http;
use RuntimeException;
use Throwable;

/**
 * Nearest shore point via the public Overpass API (OSM `natural=coastline`).
 * There is no coastline data in our own database, so this is a live lookup —
 * modern shorelines only.
 *
 * OSM draws every coastline way with the land on its LEFT, so the segment the
 * closest point lies on also tells which way is inland.
 */
final class CoastlineLookup
{
    /**
     * The closest coastline point within `$maxKm` of (lon, lat), with the
     * distance to it and the bearing that points inland from it. Null when no
     * coastline is that close; throws when Overpass can't be reached.
     *
     * @return array{lon: float, lat: float, distance_km: float, inland_bearing: float}|null
     *
     * @throws RuntimeException
     */
    public function nearest(float $lon, float $lat, float $maxKm): ?array
    {
        $best = null;
        foreach ($this->coastlines($lon, $lat, $maxKm) as $line) {
            $hit = SphericalGeometry::closestPointOnLine($lon, $lat, $line);
            if ($hit !== null && ($best === null || $hit['distance_km'] < $best['distance_km'])) {
                $best = $hit;
            }
        }

        if ($best === null || $best['distance_km'] > $maxKm) {
            return null;
        }

        return [
            'lon' => $best['lon'],
            'lat' => $best['lat'],
            'distance_km' => $best['distance_km'],
            'inland_bearing' => SphericalGeometry::normalizeBearing($best['segment_bearing'] - 90.0),
        ];
    }

    /**
     * Coastline polylines around the point, clipped to its search box.
     *
     * @return list<list<array{0: float, 1: float}>>
     */
    private function coastlines(float $lon, float $lat, float $maxKm): array
    {
        $timeout = (int) config('services.overpass.timeout', 15);
        $north = SphericalGeometry::destination($lon, $lat, $maxKm, 0)['lat'];
        $south = SphericalGeometry::destination($lon, $lat, $maxKm, 180)['lat'];
        $east = SphericalGeometry::destination($lon, $lat, $maxKm, 90)['lon'];
        $west = SphericalGeometry::destination($lon, $lat, $maxKm, 270)['lon'];

        // A box filter (not `around`, which is slow on ways) clipped to the
        // same box; the true nearest point and the max distance are worked
        // out here.
        $box = sprintf('%F,%F,%F,%F', $south, $west, $north, $east);
        $query = sprintf('[out:json][timeout:%d];way["natural"="coastline"](%s);out geom(%s);', $timeout, $box, $box);

        try {
            $response = Http::withUserAgent((string) config('services.overpass.user_agent'))
                ->timeout($timeout + 5)
                ->asForm()
                ->post((string) config('services.overpass.base_url'), ['data' => $query]);
        } catch (Throwable $e) {
            throw new RuntimeException('Overpass unreachable: '.$e->getMessage(), previous: $e);
        }

        if (! $response->successful()) {
            throw new RuntimeException("Overpass answered HTTP {$response->status()}");
        }

        // Clipping to the box can leave gaps (null nodes) inside a way; split
        // there rather than invent a segment across the gap.
        $lines = [];
        foreach ($response->json('elements') ?? [] as $element) {
            $line = [];
            foreach ([...($element['geometry'] ?? []), null] as $node) {
                if (is_array($node) && is_numeric($node['lon'] ?? null) && is_numeric($node['lat'] ?? null)) {
                    $line[] = [(float) $node['lon'], (float) $node['lat']];

                    continue;
                }
                if (count($line) >= 2) {
                    $lines[] = $line;
                }
                $line = [];
            }
        }

        return $lines;
    }
}
