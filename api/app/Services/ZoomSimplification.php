<?php

declare(strict_types=1);

namespace App\Services;

/**
 * Map zoom level → geometry simplification tolerance (degrees) and GeoJSON
 * coordinate precision (decimal digits). Lower zoom = coarser geometry and
 * fewer digits = smaller payload.
 */
class ZoomSimplification
{
    /**
     * @return array{tolerance: float, digits: int}
     */
    public static function forZoom(int $zoom): array
    {
        return match (true) {
            $zoom <= 3 => ['tolerance' => 0.5, 'digits' => 3],
            $zoom <= 6 => ['tolerance' => 0.1, 'digits' => 4],
            $zoom <= 9 => ['tolerance' => 0.02, 'digits' => 5],
            $zoom <= 12 => ['tolerance' => 0.005, 'digits' => 5],
            default => ['tolerance' => 0.0, 'digits' => 6], // no simplification
        };
    }
}
