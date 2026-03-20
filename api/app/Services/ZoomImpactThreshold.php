<?php

declare(strict_types=1);

namespace App\Services;

/**
 * Maps a map zoom level to a minimum impact score threshold.
 *
 * At low zoom levels (world/continent view) only the highest-impact entities
 * should render to avoid visual clutter. As the user zooms in, the threshold
 * drops progressively so that locally significant entities become visible.
 *
 * Zoom bands:
 *   0–2   world/hemisphere  → impact ≥ 80  (only globally significant)
 *   3–5   continent/region  → impact ≥ 60
 *   6–8   country/province  → impact ≥ 40
 *   9–11  city/district     → impact ≥ 20
 *   12+   street/local      → no threshold  (show everything)
 */
class ZoomImpactThreshold
{
    /**
     * Minimum impact score for each zoom band.
     *
     * @var list<array{max_zoom: int, min_impact: int}>
     */
    private const BANDS = [
        ['max_zoom' => 2, 'min_impact' => 80],
        ['max_zoom' => 5, 'min_impact' => 60],
        ['max_zoom' => 8, 'min_impact' => 40],
        ['max_zoom' => 11, 'min_impact' => 20],
    ];

    /**
     * Resolve the minimum impact score for a given zoom level.
     *
     * Returns null when no threshold should be applied (zoom ≥ 12).
     */
    public static function forZoom(int $zoom): ?int
    {
        foreach (self::BANDS as $band) {
            if ($zoom <= $band['max_zoom']) {
                return $band['min_impact'];
            }
        }

        return null;
    }
}
