<?php

declare(strict_types=1);

namespace Tests\Unit\Support;

use App\Support\Discover\WorldRegion;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class WorldRegionTest extends TestCase
{
    /**
     * The dozen places of the spec (§4), as [lng, lat].
     *
     * @return array<string, array{float, float, string}>
     */
    public static function knownPlaces(): array
    {
        return [
            'London' => [-0.1276, 51.5072, 'europe'],
            // East of 26° E and south of 42° N: not in either European box.
            'Istanbul' => [28.9784, 41.0082, 'middle-east-north-africa'],
            'Cairo' => [31.2357, 30.0444, 'middle-east-north-africa'],
            'Lagos' => [3.3792, 6.5244, 'sub-saharan-africa'],
            'Delhi' => [77.2090, 28.6139, 'south-asia'],
            'Beijing' => [116.4074, 39.9042, 'east-asia'],
            'Samarkand' => [66.9749, 39.6542, 'central-north-asia'],
            'Jakarta' => [106.8456, -6.2088, 'southeast-asia'],
            'Sydney' => [151.2093, -33.8688, 'oceania'],
            'New York' => [-74.0060, 40.7128, 'north-america'],
            'Mexico City' => [-99.1332, 19.4326, 'mesoamerica-caribbean'],
            'Lima' => [-77.0428, -12.0464, 'south-america'],
        ];
    }

    #[DataProvider('knownPlaces')]
    public function test_a_known_place_falls_in_its_region(float $lng, float $lat, string $expected): void
    {
        $this->assertSame($expected, WorldRegion::keyFor($lng, $lat));
        $this->assertSame(WorldRegion::NAMES[$expected], WorldRegion::nameFor($lng, $lat));
    }

    /**
     * Where boxes overlap or meet, the evaluation order decides.
     *
     * @return array<string, array{float, float, string|null}>
     */
    public static function edges(): array
    {
        return [
            'Moscow is in the eastern European box' => [37.6173, 55.7558, 'europe'],
            'Athens is west of 26° E' => [23.7275, 37.9838, 'europe'],
            'Tbilisi is south of 42° N' => [44.8271, 41.7151, 'middle-east-north-africa'],
            'Ulaanbaatar: East Asia is tried before Central & North Asia' => [106.9057, 47.8864, 'east-asia'],
            'Yakutsk is north of East Asia' => [129.7331, 62.0355, 'central-north-asia'],
            'Kabul is east of 63° E' => [69.2075, 34.5553, 'south-asia'],
            'Hanoi is north of 20° N' => [105.8342, 21.0278, 'east-asia'],
            'Manila' => [120.9842, 14.5995, 'southeast-asia'],
            'Timbuktu is north of 12° N' => [-3.0026, 16.7666, 'middle-east-north-africa'],
            'Addis Ababa' => [38.7578, 9.0054, 'sub-saharan-africa'],
            'Havana' => [-82.3666, 23.1136, 'mesoamerica-caribbean'],
            'Panama: Mesoamerica is tried before South America' => [-79.5199, 8.9824, 'mesoamerica-caribbean'],
            'Bogotá' => [-74.0721, 4.7110, 'south-america'],
            'Auckland' => [174.7633, -36.8485, 'oceania'],
            'Tahiti is east of the date line' => [-149.4068, -17.6509, 'oceania'],
            'lat 24 exactly is North America' => [-100.0, 24.0, 'north-america'],
            'lat 12 exactly is the Middle East & North Africa' => [30.0, 12.0, 'middle-east-north-africa'],
            'just south of lat 12' => [30.0, 11.99, 'sub-saharan-africa'],
            'lng 26 exactly is the western European box' => [26.0, 40.0, 'europe'],
            'Honolulu is in no box' => [-157.8583, 21.3069, null],
            'the Azores are west of 25° W' => [-25.6687, 37.7412, null],
            'mid-Atlantic' => [-40.0, 30.0, null],
            'the South Pole is not Sub-Saharan Africa' => [0.0, -90.0, null],
            'McMurdo Sound is not Oceania' => [166.6667, -77.85, null],
            'the Antarctic Peninsula is not South America' => [-63.5, -64.8, null],
            'Cape Horn still is South America' => [-67.2717, -55.9833, 'south-america'],
            'the North Pole is not Europe' => [0.0, 90.0, null],
            'Svalbard still is Europe' => [15.6356, 78.2232, 'europe'],
            'a longitude off the globe' => [200.0, 10.0, null],
            'not a number' => [NAN, 10.0, null],
        ];
    }

    #[DataProvider('edges')]
    public function test_overlaps_edges_and_empty_seas(float $lng, float $lat, ?string $expected): void
    {
        $this->assertSame($expected, WorldRegion::keyFor($lng, $lat));
    }

    public function test_names_run_west_to_east_and_cover_every_region_tried(): void
    {
        $this->assertSame([
            'north-america', 'mesoamerica-caribbean', 'south-america', 'europe', 'middle-east-north-africa',
            'sub-saharan-africa', 'central-north-asia', 'south-asia', 'east-asia', 'southeast-asia', 'oceania',
        ], array_keys(WorldRegion::NAMES));

        $tried = WorldRegion::EVALUATION_ORDER;
        sort($tried);
        $named = array_keys(WorldRegion::NAMES);
        sort($named);
        $this->assertSame($named, $tried);

        $this->assertSame('Middle East & North Africa', WorldRegion::name('middle-east-north-africa'));
        $this->assertNull(WorldRegion::name('atlantis'));
        $this->assertNull(WorldRegion::name(null));
    }

    public function test_the_sql_case_names_every_region_once_in_evaluation_order(): void
    {
        $sql = WorldRegion::sqlCase('x.lng', 'x.lat');

        $positions = array_map(fn (string $key): int|false => strpos($sql, "THEN '{$key}'"), WorldRegion::EVALUATION_ORDER);
        $this->assertNotContains(false, $positions);
        $sorted = $positions;
        sort($sorted);
        $this->assertSame($sorted, $positions);
        $this->assertStringStartsWith('CASE WHEN x.lng IS NULL OR x.lat IS NULL', $sql);
        $this->assertStringContainsString("(x.lat >= 36 AND x.lng >= -25 AND x.lng <= 26) OR (x.lat >= 42 AND x.lng >= 26 AND x.lng <= 60) THEN 'europe'", $sql);
        $this->assertStringEndsWith(' END', $sql);
    }
}
