<?php

declare(strict_types=1);

namespace App\Support\MapStory;

/**
 * GeoJSON geometry from map-story coordinates, simplified for the ambient
 * layer (about 0.01°, 3 decimals), the simplification of step entities' atlas
 * geometry, and the extent of a set of coordinates.
 */
final class MapStoryGeometry
{
    /** Douglas–Peucker tolerance in degrees (about 1 km). */
    public const TOLERANCE = 0.01;

    /** Coordinate decimals kept (about 100 m). */
    public const DECIMALS = 3;

    /**
     * A step entity's atlas area is simplified at these tolerances in turn
     * until its GeoJSON fits ENTITY_MAX_BYTES (the last one is kept anyway),
     * so a story with a few empires stays well under a megabyte or two.
     */
    public const ENTITY_TOLERANCES = [self::TOLERANCE, 0.03, 0.1];

    public const ENTITY_MAX_BYTES = 150_000;

    /**
     * @param  array{0: int|float, 1: int|float}  $at
     * @return array{type: 'Point', coordinates: array{0: float, 1: float}}
     */
    public static function point(array $at): array
    {
        return ['type' => 'Point', 'coordinates' => self::round($at)];
    }

    /**
     * @param  list<array{0: int|float, 1: int|float}>  $line
     * @return array{type: 'LineString', coordinates: list<array{0: float, 1: float}>}|null
     */
    public static function line(array $line): ?array
    {
        $points = self::dedupe(array_map(self::round(...), self::simplify($line, self::TOLERANCE)));

        return count($points) < 2 ? null : ['type' => 'LineString', 'coordinates' => $points];
    }

    /**
     * One ring (a Polygon) or a list of rings (a MultiPolygon of simple polygons).
     *
     * @param  list<mixed>  $area
     * @return array{type: 'Polygon'|'MultiPolygon', coordinates: list<mixed>}|null
     */
    public static function area(array $area): ?array
    {
        if (! MapStoryDocument::isMulti($area)) {
            $ring = self::ring($area);

            return $ring === null ? null : ['type' => 'Polygon', 'coordinates' => [$ring]];
        }
        $polygons = [];
        foreach ($area as $ring) {
            $ring = is_array($ring) ? self::ring($ring) : null;
            if ($ring !== null) {
                $polygons[] = [$ring];
            }
        }

        return $polygons === [] ? null : ['type' => 'MultiPolygon', 'coordinates' => $polygons];
    }

    /**
     * A closed, simplified, rounded ring; when simplifying collapses it, the
     * rounded ring as given; null when even that has no area.
     *
     * @param  list<mixed>  $ring
     * @return list<array{0: float, 1: float}>|null
     */
    private static function ring(array $ring): ?array
    {
        $points = array_values(array_filter($ring, MapStoryDocument::point(...)));
        if (count($points) < 3) {
            return null;
        }
        if ($points[0] !== $points[count($points) - 1]) {
            $points[] = $points[0];
        }
        foreach ([self::simplify($points, self::TOLERANCE), $points] as $candidate) {
            $closed = self::dedupe(array_map(self::round(...), $candidate));
            if (count($closed) >= 4) {
                return $closed;
            }
        }

        return null;
    }

    /**
     * Douglas–Peucker: the points that keep the line within `$tolerance`.
     *
     * @param  list<array{0: int|float, 1: int|float}>  $points
     * @return list<array{0: int|float, 1: int|float}>
     */
    public static function simplify(array $points, float $tolerance): array
    {
        $n = count($points);
        if ($n < 3) {
            return $points;
        }
        $keep = [0 => true, $n - 1 => true];
        $stack = [[0, $n - 1]];
        while ($stack !== []) {
            [$a, $b] = array_pop($stack);
            $far = null;
            $distance = $tolerance;
            for ($i = $a + 1; $i < $b; $i++) {
                $d = self::segmentDistance($points[$i], $points[$a], $points[$b]);
                if ($d > $distance) {
                    [$far, $distance] = [$i, $d];
                }
            }
            if ($far !== null) {
                $keep[$far] = true;
                $stack[] = [$a, $far];
                $stack[] = [$far, $b];
            }
        }
        ksort($keep);

        return array_values(array_map(fn (int $i) => $points[$i], array_keys($keep)));
    }

    /**
     * [west, south, east, north] of every [lon, lat] pair nested anywhere in
     * `$values` (points, lines, rings, lists of rings, GeoJSON coordinates).
     *
     * @param  iterable<mixed>  $values
     * @return array{0: float, 1: float, 2: float, 3: float}|null
     */
    public static function extent(iterable $values): ?array
    {
        $box = null;
        $stack = [];
        foreach ($values as $value) {
            $stack[] = $value;
        }
        while ($stack !== []) {
            $value = array_pop($stack);
            if (MapStoryDocument::point($value)) {
                [$x, $y] = [(float) $value[0], (float) $value[1]];
                $box = $box === null ? [$x, $y, $x, $y] : [min($box[0], $x), min($box[1], $y), max($box[2], $x), max($box[3], $y)];
            } elseif (is_array($value)) {
                array_push($stack, ...array_values($value));
            }
        }

        return $box;
    }

    /**
     * @param  array{0: int|float, 1: int|float}  $p
     * @param  array{0: int|float, 1: int|float}  $a
     * @param  array{0: int|float, 1: int|float}  $b
     */
    private static function segmentDistance(array $p, array $a, array $b): float
    {
        [$dx, $dy] = [$b[0] - $a[0], $b[1] - $a[1]];
        $length = $dx * $dx + $dy * $dy;
        $t = $length === 0 || $length === 0.0 ? 0.0 : max(0.0, min(1.0, (($p[0] - $a[0]) * $dx + ($p[1] - $a[1]) * $dy) / $length));

        return hypot($p[0] - ($a[0] + $t * $dx), $p[1] - ($a[1] + $t * $dy));
    }

    /**
     * @param  array{0: int|float, 1: int|float}  $point
     * @return array{0: float, 1: float}
     */
    private static function round(array $point): array
    {
        return [round((float) $point[0], self::DECIMALS), round((float) $point[1], self::DECIMALS)];
    }

    /**
     * Drop consecutive repeats (rounding can make neighbours equal).
     *
     * @param  list<array{0: float, 1: float}>  $points
     * @return list<array{0: float, 1: float}>
     */
    private static function dedupe(array $points): array
    {
        $out = [];
        foreach ($points as $point) {
            if ($out === [] || $out[count($out) - 1] !== $point) {
                $out[] = $point;
            }
        }

        return $out;
    }
}
