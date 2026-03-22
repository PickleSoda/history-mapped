<?php

declare(strict_types=1);

namespace App\Support\Geometry;

/**
 * Normalize request GeoJSON payloads into geometry objects accepted by ST_GeomFromGeoJSON.
 */
final class NormalizeGeoJsonForPostgis
{
    /**
     * @param  array<string, mixed>|null  $payload
     * @return array<string, mixed>|null
     */
    public static function normalize(?array $payload): ?array
    {
        if ($payload === null) {
            return null;
        }

        $type = $payload['type'] ?? null;
        if (! is_string($type)) {
            return $payload;
        }

        if ($type === 'Feature') {
            $geometry = $payload['geometry'] ?? null;

            return is_array($geometry) ? self::normalize($geometry) : null;
        }

        if ($type === 'FeatureCollection') {
            $features = $payload['features'] ?? null;
            if (! is_array($features)) {
                return null;
            }

            $geometries = [];
            foreach ($features as $feature) {
                if (! is_array($feature)) {
                    continue;
                }

                $geometry = $feature['geometry'] ?? null;
                if (! is_array($geometry)) {
                    continue;
                }

                $normalized = self::normalize($geometry);
                if (! is_array($normalized)) {
                    continue;
                }

                if (($normalized['type'] ?? null) === 'GeometryCollection' && is_array($normalized['geometries'] ?? null)) {
                    foreach ($normalized['geometries'] as $childGeometry) {
                        if (is_array($childGeometry)) {
                            $geometries[] = $childGeometry;
                        }
                    }

                    continue;
                }

                $geometries[] = $normalized;
            }

            if (count($geometries) === 0) {
                return null;
            }

            if (count($geometries) === 1) {
                return $geometries[0];
            }

            return ['type' => 'GeometryCollection', 'geometries' => $geometries];
        }

        if ($type === 'GeometryCollection') {
            $children = $payload['geometries'] ?? null;
            if (! is_array($children)) {
                return null;
            }

            $geometries = [];
            foreach ($children as $child) {
                if (! is_array($child)) {
                    continue;
                }

                $normalized = self::normalize($child);
                if (is_array($normalized)) {
                    if (($normalized['type'] ?? null) === 'GeometryCollection' && is_array($normalized['geometries'] ?? null)) {
                        foreach ($normalized['geometries'] as $childGeometry) {
                            if (is_array($childGeometry)) {
                                $geometries[] = $childGeometry;
                            }
                        }
                    } else {
                        $geometries[] = $normalized;
                    }
                }
            }

            if (count($geometries) === 0) {
                return null;
            }

            return ['type' => 'GeometryCollection', 'geometries' => $geometries];
        }

        return $payload;
    }
}
