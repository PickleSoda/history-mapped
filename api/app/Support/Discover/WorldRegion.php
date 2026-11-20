<?php

declare(strict_types=1);

namespace App\Support\Discover;

/**
 * The eleven world regions of the Discover feed, decided by a map point
 * (docs/superpowers/specs/2026-11-20-discover-feed-design.md, §4).
 *
 * Region tags cover only a fifth of the map entities and are skewed, so the
 * region comes from where the point is. Each region is one or two boxes in
 * degrees; boxes overlap, and the first match in EVALUATION_ORDER wins. A
 * point in no box (mid-ocean, Hawaii, the Azores) has no region.
 *
 * The polar caps have none either. Three boxes have no southern edge (South
 * America, Sub-Saharan Africa, Oceania) and Europe has no northern one, so
 * without a limit Amundsen's South Pole expedition is an event of
 * Sub-Saharan Africa and a point at the North Pole is in Europe. Regions
 * therefore stop at 60° S (the Antarctic Treaty line) and 85° N.
 *
 * A range "a…b" includes both ends; the one-sided bounds are as written
 * (`lat >= 24`, `lat < 13`). keyFor() decides in PHP and sqlCase() writes the
 * same table as a SQL CASE, so a query can group by region without bringing
 * its rows to PHP.
 */
final class WorldRegion
{
    /**
     * key => display name, in display order: west to east.
     *
     * @var array<string, string>
     */
    public const NAMES = [
        'north-america' => 'North America',
        'mesoamerica-caribbean' => 'Mesoamerica & the Caribbean',
        'south-america' => 'South America',
        'europe' => 'Europe',
        'middle-east-north-africa' => 'Middle East & North Africa',
        'sub-saharan-africa' => 'Sub-Saharan Africa',
        'central-north-asia' => 'Central & North Asia',
        'south-asia' => 'South Asia',
        'east-asia' => 'East Asia',
        'southeast-asia' => 'Southeast Asia',
        'oceania' => 'Oceania',
    ];

    /**
     * The order the boxes are tried in. Europe is cut out of the Old World
     * first, East Asia before Central & North Asia (Mongolia and Manchuria are
     * East Asia), Oceania before the Americas.
     *
     * @var list<string>
     */
    public const EVALUATION_ORDER = [
        'europe',
        'middle-east-north-africa',
        'sub-saharan-africa',
        'south-asia',
        'east-asia',
        'southeast-asia',
        'central-north-asia',
        'oceania',
        'north-america',
        'mesoamerica-caribbean',
        'south-america',
    ];

    /**
     * key => boxes (any may match); a box is a list of bounds that must all
     * hold, each written "axis operator" => degrees.
     *
     * @var array<string, list<array<string, int>>>
     */
    private const BOXES = [
        'north-america' => [
            ['lng >=' => -170, 'lng <=' => -50, 'lat >=' => 24],
        ],
        'mesoamerica-caribbean' => [
            ['lng >=' => -120, 'lng <=' => -58, 'lat >=' => 7, 'lat <=' => 24],
        ],
        'south-america' => [
            ['lng >=' => -93, 'lng <=' => -30, 'lat <' => 13],
        ],
        'europe' => [
            ['lat >=' => 36, 'lng >=' => -25, 'lng <=' => 26],
            ['lat >=' => 42, 'lng >=' => 26, 'lng <=' => 60],
        ],
        'middle-east-north-africa' => [
            ['lat >=' => 12, 'lat <=' => 42, 'lng >=' => -18, 'lng <=' => 63],
        ],
        'sub-saharan-africa' => [
            ['lat <' => 12, 'lng >=' => -20, 'lng <=' => 52],
        ],
        'central-north-asia' => [
            ['lat >=' => 37, 'lng >=' => 45, 'lng <=' => 180],
        ],
        'south-asia' => [
            ['lat >=' => 5, 'lat <=' => 37, 'lng >=' => 60, 'lng <=' => 93],
        ],
        'east-asia' => [
            ['lat >=' => 20, 'lat <=' => 55, 'lng >=' => 93, 'lng <=' => 150],
        ],
        'southeast-asia' => [
            ['lat >=' => -11, 'lat <=' => 20, 'lng >=' => 92, 'lng <=' => 141],
        ],
        'oceania' => [
            ['lat <' => -8, 'lng >=' => 110],
            ['lat <' => -8, 'lng <=' => -130],
        ],
    ];

    /** South of this latitude is Antarctica: no region. */
    public const SOUTH_LIMIT = -60;

    /** North of this latitude is the polar sea: no region (Svalbard is at 80). */
    public const NORTH_LIMIT = 85;

    /** The region key of a point, or null when it lies in no box. */
    public static function keyFor(float $lng, float $lat): ?string
    {
        if (! self::onTheGlobe($lng, $lat)) {
            return null;
        }

        foreach (self::EVALUATION_ORDER as $key) {
            foreach (self::BOXES[$key] as $box) {
                if (self::inBox($box, $lng, $lat)) {
                    return $key;
                }
            }
        }

        return null;
    }

    /** The region's display name ("East Asia") for a point, or null. */
    public static function nameFor(float $lng, float $lat): ?string
    {
        $key = self::keyFor($lng, $lat);

        return $key === null ? null : self::NAMES[$key];
    }

    /** The display name of a region key; null for an unknown key. */
    public static function name(?string $key): ?string
    {
        return $key === null ? null : (self::NAMES[$key] ?? null);
    }

    /**
     * The same decision as keyFor() as a SQL CASE expression that yields the
     * region key or NULL. `$lng` and `$lat` are SQL expressions (column names
     * or the like) written by the caller, never user input.
     */
    public static function sqlCase(string $lng, string $lat): string
    {
        $sql = "CASE WHEN {$lng} IS NULL OR {$lat} IS NULL OR {$lng} < -180 OR {$lng} > 180"
            ." OR {$lat} < ".self::SOUTH_LIMIT." OR {$lat} > ".self::NORTH_LIMIT.' THEN NULL';

        foreach (self::EVALUATION_ORDER as $key) {
            $boxes = [];
            foreach (self::BOXES[$key] as $box) {
                $bounds = [];
                foreach ($box as $bound => $degrees) {
                    [$axis, $operator] = explode(' ', $bound);
                    $bounds[] = ($axis === 'lng' ? $lng : $lat)." {$operator} {$degrees}";
                }
                $boxes[] = '('.implode(' AND ', $bounds).')';
            }
            $sql .= ' WHEN '.implode(' OR ', $boxes)." THEN '{$key}'";
        }

        return $sql.' END';
    }

    /** A real longitude, and a latitude between the polar caps. */
    private static function onTheGlobe(float $lng, float $lat): bool
    {
        return $lng >= -180 && $lng <= 180 && $lat >= self::SOUTH_LIMIT && $lat <= self::NORTH_LIMIT;
    }

    /** @param array<string, int> $box */
    private static function inBox(array $box, float $lng, float $lat): bool
    {
        foreach ($box as $bound => $degrees) {
            [$axis, $operator] = explode(' ', $bound);
            $value = $axis === 'lng' ? $lng : $lat;

            $holds = match ($operator) {
                '>=' => $value >= $degrees,
                '<=' => $value <= $degrees,
                '<' => $value < $degrees,
            };
            if (! $holds) {
                return false;
            }
        }

        return true;
    }
}
