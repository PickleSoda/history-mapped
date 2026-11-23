<?php

declare(strict_types=1);

namespace Tests\Feature\Tags;

use App\Models\Tag;
use App\Support\Tags\RegionFootprint;
use Database\Seeders\TagSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class RegionFootprintTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(TagSeeder::class);
    }

    /** @return list<string> the regions whose footprint holds the point */
    private function regionsAt(float $lng, float $lat): array
    {
        return array_map(fn (object $row): string => $row->tag, DB::select(
            'WITH footprints AS ('.RegionFootprint::sql().')
             SELECT DISTINCT tag FROM footprints
             WHERE ST_Intersects(ST_SetSRID(ST_MakePoint(?, ?), 4326), box)
             ORDER BY tag',
            [$lng, $lat],
        ));
    }

    /**
     * place => [lng, lat, regions it must be in, regions it must not be in]
     *
     * @return array<string, array{float, float, list<string>, list<string>}>
     */
    public static function places(): array
    {
        return [
            'Ypres' => [2.89, 50.85, ['europe', 'western-europe', 'atlantic'], ['asia', 'middle-east', 'british-isles', 'central-europe']],
            'London' => [-0.13, 51.51, ['europe', 'british-isles'], ['western-europe']],
            'Paris' => [2.35, 48.86, ['europe', 'western-europe'], ['british-isles', 'iberia', 'italy']],
            'Rome' => [12.48, 41.89, ['europe', 'italy', 'mediterranean'], ['balkans', 'africa', 'asia']],
            'Vienna' => [16.37, 48.21, ['central-europe'], ['balkans', 'italy', 'eastern-europe']],
            'Constantinople' => [28.98, 41.01, ['europe', 'balkans', 'greece', 'asia', 'anatolia', 'mediterranean'], ['africa']],
            'Kyiv' => [30.52, 50.45, ['europe', 'eastern-europe', 'central-asia'], ['central-europe', 'balkans']],
            'Cairo' => [31.24, 30.04, ['africa', 'egypt', 'north-africa', 'mediterranean'], ['asia', 'levant', 'middle-east', 'nubia']],
            'Jerusalem' => [35.23, 31.78, ['asia', 'middle-east', 'levant'], ['africa', 'egypt', 'arabia']],
            'Nicosia' => [33.36, 35.17, ['levant', 'greece'], ['africa', 'egypt']],
            'Baghdad' => [44.36, 33.31, ['mesopotamia', 'iran', 'silk-roads'], ['levant', 'arabia', 'europe']],
            'Mecca' => [39.83, 21.42, ['arabia', 'indian-ocean'], ['africa', 'nubia', 'east-africa']],
            'Samarkand' => [66.96, 39.65, ['central-asia', 'iran', 'silk-roads'], ['south-asia', 'china']],
            'Delhi' => [77.21, 28.61, ['south-asia'], ['central-asia', 'china', 'east-asia']],
            'Beijing' => [116.4, 39.9, ['china', 'east-asia'], ['korea', 'japan', 'central-asia']],
            'Seoul' => [126.98, 37.57, ['korea'], ['china', 'japan']],
            'Fukuoka' => [130.4, 33.59, ['japan'], ['korea', 'china']],
            'Hanoi' => [105.85, 21.03, ['southeast-asia'], ['china']],
            'Sydney' => [151.21, -33.87, ['oceania'], ['asia', 'southeast-asia']],
            'Honolulu' => [-157.86, 21.31, ['oceania', 'north-america', 'americas'], ['asia']],
            'Mexico City' => [-99.13, 19.43, ['americas', 'mesoamerica', 'north-america'], ['south-america', 'caribbean']],
            'Havana' => [-82.37, 23.11, ['caribbean'], ['mesoamerica', 'south-america']],
            'Cusco' => [-71.97, -13.53, ['americas', 'south-america', 'andes'], ['mesoamerica']],
            'Timbuktu' => [-3.0, 16.77, ['africa', 'west-africa', 'north-africa'], ['europe', 'east-africa']],
            'Great Zimbabwe' => [30.93, -20.27, ['africa', 'southern-africa', 'indian-ocean'], ['east-africa', 'west-africa']],
            'Kilwa' => [39.51, -8.96, ['africa', 'east-africa', 'indian-ocean'], ['southern-africa']],
            'Reykjavik' => [-21.9, 64.15, ['europe', 'northern-europe', 'atlantic', 'polar'], ['americas']],
        ];
    }

    /**
     * @param  list<string>  $in
     * @param  list<string>  $out
     */
    #[DataProvider('places')]
    public function test_well_known_places_fall_in_their_regions(float $lng, float $lat, array $in, array $out): void
    {
        $regions = $this->regionsAt($lng, $lat);

        foreach ($in as $region) {
            $this->assertContains($region, $regions);
        }
        foreach ($out as $region) {
            $this->assertNotContains($region, $regions);
        }
    }

    public function test_every_region_but_global_has_a_footprint_and_every_box_is_a_region(): void
    {
        $regions = Tag::where('facet', 'region')->pluck('slug')->sort()->values()->all();
        $withFootprint = collect(DB::select('SELECT DISTINCT tag FROM ('.RegionFootprint::sql().') f'))
            ->pluck('tag')->sort()->values()->all();

        $this->assertSame(array_values(array_diff($regions, ['global'])), $withFootprint);
        $this->assertSame([], array_diff(array_keys(RegionFootprint::BOXES), $regions));
    }

    public function test_boxes_are_well_formed(): void
    {
        foreach (RegionFootprint::BOXES as $slug => $boxes) {
            foreach ($boxes as [$west, $south, $east, $north]) {
                $this->assertTrue($west >= -180 && $west < $east && $east <= 180, "{$slug}: longitudes");
                $this->assertTrue($south >= -90 && $south < $north && $north <= 90, "{$slug}: latitudes");
            }
        }
    }
}
