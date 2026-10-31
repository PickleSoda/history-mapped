<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Geo\SphericalGeometry as G;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class SphericalGeometryTest extends TestCase
{
    /** Kilometres in one degree of a great circle. */
    private const DEG_KM = 2 * M_PI * G::EARTH_RADIUS_KM / 360;

    public function test_rome_to_paris_distance(): void
    {
        $km = G::distanceKm(12.4964, 41.9028, 2.3522, 48.8566);

        $this->assertGreaterThan(1100, $km);
        $this->assertLessThan(1112, $km);
    }

    public function test_one_degree_north_and_east_at_the_equator(): void
    {
        $north = G::destination(0, 0, self::DEG_KM, 0);
        $this->assertEqualsWithDelta(1.0, $north['lat'], 1e-6);
        $this->assertEqualsWithDelta(0.0, $north['lon'], 1e-6);

        $east = G::destination(0, 0, self::DEG_KM, 90);
        $this->assertEqualsWithDelta(1.0, $east['lon'], 1e-6);
        $this->assertEqualsWithDelta(0.0, $east['lat'], 1e-6);
    }

    public function test_destination_round_trips_through_distance_and_bearing(): void
    {
        $to = G::destination(12.4964, 41.9028, 250, 22.5);

        $this->assertEqualsWithDelta(250, G::distanceKm(12.4964, 41.9028, $to['lon'], $to['lat']), 1e-6);
        $this->assertEqualsWithDelta(22.5, G::initialBearing(12.4964, 41.9028, $to['lon'], $to['lat']), 1e-6);
    }

    public function test_destination_wraps_the_antimeridian(): void
    {
        $to = G::destination(179.5, 0, self::DEG_KM, 90);

        $this->assertEqualsWithDelta(-179.5, $to['lon'], 1e-6);
        $this->assertEqualsWithDelta(self::DEG_KM, G::distanceKm(179.5, 0, -179.5, 0), 1e-6);
    }

    public function test_intermediate_points(): void
    {
        $mid = G::intermediate(10, 0, 10, 20, 0.5);
        $this->assertEqualsWithDelta(10.0, $mid['lon'], 1e-9);
        $this->assertEqualsWithDelta(10.0, $mid['lat'], 1e-9);

        // Midway is equidistant from both ends; the ends are the anchors.
        $mid = G::intermediate(12.4964, 41.9028, 2.3522, 48.8566, 0.5);
        $this->assertEqualsWithDelta(
            G::distanceKm(12.4964, 41.9028, $mid['lon'], $mid['lat']),
            G::distanceKm(2.3522, 48.8566, $mid['lon'], $mid['lat']),
            1e-6,
        );
        $this->assertEqualsWithDelta(12.4964, G::intermediate(12.4964, 41.9028, 2.3522, 48.8566, 0)['lon'], 1e-9);
        $this->assertEqualsWithDelta(48.8566, G::intermediate(12.4964, 41.9028, 2.3522, 48.8566, 1)['lat'], 1e-9);

        // A quarter of the way covers a quarter of the distance.
        $quarter = G::intermediate(12.4964, 41.9028, 2.3522, 48.8566, 0.25);
        $this->assertEqualsWithDelta(
            G::distanceKm(12.4964, 41.9028, 2.3522, 48.8566) / 4,
            G::distanceKm(12.4964, 41.9028, $quarter['lon'], $quarter['lat']),
            1e-6,
        );
    }

    public function test_identical_points_have_no_path(): void
    {
        $this->assertSame(['lon' => 5.0, 'lat' => 5.0], G::intermediate(5, 5, 5, 5, 0.5));
    }

    public function test_initial_bearing(): void
    {
        $this->assertEqualsWithDelta(0.0, G::initialBearing(0, 0, 0, 10), 1e-9);
        $this->assertEqualsWithDelta(90.0, G::initialBearing(0, 0, 10, 0), 1e-9);
        $this->assertEqualsWithDelta(270.0, G::initialBearing(0, 0, -10, 0), 1e-9);
    }

    /** @return array<string, array{0: string|int|float, 1: ?float}> */
    public static function directions(): array
    {
        return [
            'abbrev' => ['N', 0.0],
            'three-letter abbrev' => ['nne', 22.5],
            'hyphenated' => ['north-east', 45.0],
            'one word' => ['Northeast', 45.0],
            'two words' => ['North East', 45.0],
            'three words' => ['east north east', 67.5],
            'filler' => ['due west', 270.0],
            'adverb' => ['southwards', 180.0],
            'by east' => ['north by east', 11.25],
            'by west' => ['north by west', 348.75],
            'degrees' => ['45', 45.0],
            'degree sign' => ['135°', 135.0],
            'number' => [400, 40.0],
            'negative' => [-90, 270.0],
            'nonsense' => ['up', null],
            'not a direction' => ['toward the sea', null],
            'contradiction' => ['north south', null],
        ];
    }

    #[DataProvider('directions')]
    public function test_parse_direction(string|int|float $input, ?float $expected): void
    {
        $this->assertSame($expected, G::parseDirection($input));
    }

    public function test_compass_label(): void
    {
        $this->assertSame('NNE', G::compassLabel(22.5));
        $this->assertSame('N', G::compassLabel(359));
        $this->assertSame('E', G::compassLabel(91));
        $this->assertSame('NW', G::compassLabel(-45));
    }

    public function test_closest_point_on_line(): void
    {
        // An east-running coast one degree north of the query point.
        $hit = G::closestPointOnLine(1, 0, [[0, 1], [2, 1]]);

        $this->assertNotNull($hit);
        $this->assertEqualsWithDelta(1.0, $hit['lon'], 1e-6);
        $this->assertEqualsWithDelta(1.0, $hit['lat'], 1e-6);
        $this->assertEqualsWithDelta(self::DEG_KM, $hit['distance_km'], 0.5);
        $this->assertEqualsWithDelta(90.0, $hit['segment_bearing'], 0.1);
    }

    public function test_closest_point_clamps_to_the_segment_end(): void
    {
        $hit = G::closestPointOnLine(5, 0, [[0, 0], [1, 0], [2, 1]]);

        $this->assertEqualsWithDelta(2.0, $hit['lon'], 1e-6);
        $this->assertEqualsWithDelta(1.0, $hit['lat'], 1e-6);
    }

    public function test_closest_point_needs_a_segment(): void
    {
        $this->assertNull(G::closestPointOnLine(0, 0, [[1, 1]]));
    }
}
