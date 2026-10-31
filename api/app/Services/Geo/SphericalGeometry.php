<?php

declare(strict_types=1);

namespace App\Services\Geo;

/**
 * Great-circle math on a spherical Earth (lon/lat in degrees, distances in km).
 *
 * Backs the admin AI's placement tools, so a small model only has to turn a
 * phrase ("20 km NNE of Rome", "midway between A and B", "on the shore near X")
 * into an anchor and an operation — the trigonometry happens here. A sphere is
 * within ~0.5% of the ellipsoid, far finer than any historical placement.
 */
final class SphericalGeometry
{
    /** IUGG mean Earth radius. */
    public const EARTH_RADIUS_KM = 6371.0088;

    /** 16-point compass rose, clockwise from north. */
    private const POINTS = [
        'n' => 0.0, 'nne' => 22.5, 'ne' => 45.0, 'ene' => 67.5,
        'e' => 90.0, 'ese' => 112.5, 'se' => 135.0, 'sse' => 157.5,
        's' => 180.0, 'ssw' => 202.5, 'sw' => 225.0, 'wsw' => 247.5,
        'w' => 270.0, 'wnw' => 292.5, 'nw' => 315.0, 'nnw' => 337.5,
    ];

    /** One point of the 32-point rose ("north by east" = N + 11.25°). */
    private const BY_STEP = 11.25;

    /** Words a direction phrase may carry around the compass words ("due north"). */
    private const FILLER_WORDS = ['due', 'the', 'of', 'to', 'toward', 'towards', 'direction', 'heading'];

    /**
     * The point `$distanceKm` from (lon, lat) along initial bearing `$bearing`
     * (degrees clockwise from north).
     *
     * @return array{lon: float, lat: float}
     */
    public static function destination(float $lon, float $lat, float $distanceKm, float $bearing): array
    {
        $phi1 = deg2rad($lat);
        $lambda1 = deg2rad($lon);
        $theta = deg2rad($bearing);
        $delta = $distanceKm / self::EARTH_RADIUS_KM;

        $phi2 = asin(sin($phi1) * cos($delta) + cos($phi1) * sin($delta) * cos($theta));
        $lambda2 = $lambda1 + atan2(
            sin($theta) * sin($delta) * cos($phi1),
            cos($delta) - sin($phi1) * sin($phi2),
        );

        return ['lon' => self::normalizeLon(rad2deg($lambda2)), 'lat' => rad2deg($phi2)];
    }

    /**
     * The point a `$fraction` (0 = A, 1 = B) of the way along the great circle
     * from A to B. Antipodal pairs have no unique path; A is returned for them.
     *
     * @return array{lon: float, lat: float}
     */
    public static function intermediate(float $lonA, float $latA, float $lonB, float $latB, float $fraction): array
    {
        $delta = self::distanceKm($lonA, $latA, $lonB, $latB) / self::EARTH_RADIUS_KM;
        if ($delta < 1e-12 || abs(sin($delta)) < 1e-12) {
            return ['lon' => self::normalizeLon($lonA), 'lat' => $latA];
        }

        $phi1 = deg2rad($latA);
        $lambda1 = deg2rad($lonA);
        $phi2 = deg2rad($latB);
        $lambda2 = deg2rad($lonB);

        $a = sin((1 - $fraction) * $delta) / sin($delta);
        $b = sin($fraction * $delta) / sin($delta);
        $x = $a * cos($phi1) * cos($lambda1) + $b * cos($phi2) * cos($lambda2);
        $y = $a * cos($phi1) * sin($lambda1) + $b * cos($phi2) * sin($lambda2);
        $z = $a * sin($phi1) + $b * sin($phi2);

        return [
            'lon' => self::normalizeLon(rad2deg(atan2($y, $x))),
            'lat' => rad2deg(atan2($z, sqrt($x * $x + $y * $y))),
        ];
    }

    /** Haversine great-circle distance. */
    public static function distanceKm(float $lonA, float $latA, float $lonB, float $latB): float
    {
        $dPhi = deg2rad($latB - $latA);
        $dLambda = deg2rad($lonB - $lonA);
        $h = sin($dPhi / 2) ** 2
            + cos(deg2rad($latA)) * cos(deg2rad($latB)) * sin($dLambda / 2) ** 2;

        return 2 * self::EARTH_RADIUS_KM * asin(min(1.0, sqrt($h)));
    }

    /** Initial bearing from A toward B, degrees clockwise from north in [0, 360). */
    public static function initialBearing(float $lonA, float $latA, float $lonB, float $latB): float
    {
        $phi1 = deg2rad($latA);
        $phi2 = deg2rad($latB);
        $dLambda = deg2rad($lonB - $lonA);

        $theta = atan2(
            sin($dLambda) * cos($phi2),
            cos($phi1) * sin($phi2) - sin($phi1) * cos($phi2) * cos($dLambda),
        );

        return self::normalizeBearing(rad2deg($theta));
    }

    /**
     * Parse a direction as a model or a source text gives it: a bearing in
     * degrees ("45", "45°", 45) or compass words in any spelling — "N", "NNE",
     * "north-east", "northeast", "North East", "northwards", "north by east".
     * Null when it can't be read.
     */
    public static function parseDirection(string|int|float $direction): ?float
    {
        if (is_int($direction) || is_float($direction)) {
            return self::normalizeBearing((float) $direction);
        }

        $text = strtolower(trim($direction));
        if (preg_match('/^(-?\d+(?:\.\d+)?)\s*(?:°|deg(?:rees?)?)?$/', $text, $m) === 1) {
            return self::normalizeBearing((float) $m[1]);
        }

        // "north by east": one 32-point step from the first point toward the second.
        $parts = preg_split('/\s+by\s+/', $text);
        if (is_array($parts) && count($parts) === 2) {
            $base = self::compassPoint($parts[0]);
            $toward = self::compassPoint($parts[1]);
            if ($base === null || $toward === null) {
                return null;
            }
            $turn = fmod($toward - $base + 540.0, 360.0) - 180.0;

            return self::normalizeBearing($base + ($turn >= 0 ? self::BY_STEP : -self::BY_STEP));
        }

        return self::compassPoint($text);
    }

    /** The nearest 16-point compass label for a bearing, e.g. 22.5 → "NNE". */
    public static function compassLabel(float $bearing): string
    {
        $index = (int) round(self::normalizeBearing($bearing) / 22.5) % 16;

        return strtoupper(array_keys(self::POINTS)[$index]);
    }

    /**
     * Closest point on a polyline to (lon, lat), with the distance to it and
     * the bearing of the segment it lies on (in the polyline's own direction).
     * Uses a local equirectangular projection centered on the query point —
     * accurate to well under 1% within a few hundred km — and reports the true
     * great-circle distance.
     *
     * @param  list<array{0: float, 1: float}>  $line  [[lon, lat], ...]
     * @return array{lon: float, lat: float, distance_km: float, segment_bearing: float}|null
     */
    public static function closestPointOnLine(float $lon, float $lat, array $line): ?array
    {
        if (count($line) < 2) {
            return null;
        }

        $kx = cos(deg2rad($lat)) * self::EARTH_RADIUS_KM * M_PI / 180;
        $ky = self::EARTH_RADIUS_KM * M_PI / 180;
        $project = fn (array $p): array => [
            (fmod($p[0] - $lon + 540.0, 360.0) - 180.0) * $kx,
            ($p[1] - $lat) * $ky,
        ];

        $best = null;
        for ($i = 0, $n = count($line) - 1; $i < $n; $i++) {
            [$ax, $ay] = $project($line[$i]);
            [$bx, $by] = $project($line[$i + 1]);
            $dx = $bx - $ax;
            $dy = $by - $ay;
            $len2 = $dx * $dx + $dy * $dy;
            $t = $len2 > 0 ? max(0.0, min(1.0, -($ax * $dx + $ay * $dy) / $len2)) : 0.0;
            $px = $ax + $t * $dx;
            $py = $ay + $t * $dy;
            $d2 = $px * $px + $py * $py;

            if ($best === null || $d2 < $best['d2']) {
                $best = ['d2' => $d2, 'x' => $px, 'y' => $py, 'i' => $i];
            }
        }

        $point = [
            'lon' => self::normalizeLon($lon + $best['x'] / $kx),
            'lat' => $lat + $best['y'] / $ky,
        ];
        [$a, $b] = [$line[$best['i']], $line[$best['i'] + 1]];

        return [
            ...$point,
            'distance_km' => self::distanceKm($lon, $lat, $point['lon'], $point['lat']),
            'segment_bearing' => self::initialBearing($a[0], $a[1], $b[0], $b[1]),
        ];
    }

    public static function normalizeBearing(float $degrees): float
    {
        $b = fmod($degrees, 360.0);

        return $b < 0 ? $b + 360.0 : $b;
    }

    public static function normalizeLon(float $lon): float
    {
        return fmod($lon + 540.0, 360.0) - 180.0;
    }

    /**
     * "north-east" / "northeast" / "NE" / "due north" / "northwards" → a
     * bearing; null when any word isn't a compass word or a filler.
     */
    private static function compassPoint(string $text): ?float
    {
        $tokens = preg_split('/[\s\-_\/]+/', strtolower(trim($text)), -1, PREG_SPLIT_NO_EMPTY);
        if (! is_array($tokens) || $tokens === []) {
            return null;
        }

        $letters = '';
        foreach ($tokens as $token) {
            if (in_array($token, self::FILLER_WORDS, true)) {
                continue;
            }
            $short = preg_replace(
                ['/north(?:ern|erly|wards?)?/', '/south(?:ern|erly|wards?)?/', '/east(?:ern|erly|wards?)?/', '/west(?:ern|erly|wards?)?/'],
                ['n', 's', 'e', 'w'],
                $token,
            );
            if (! is_string($short) || preg_match('/^[nsew]+$/', $short) !== 1) {
                return null;
            }
            $letters .= $short;
        }

        return self::POINTS[$letters] ?? null;
    }
}
