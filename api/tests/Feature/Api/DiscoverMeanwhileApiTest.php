<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Support\Discover\WorldRegion;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * GET /api/v1/discover/meanwhile: one year across the world regions, chosen
 * from the tile feature table.
 */
class DiscoverMeanwhileApiTest extends TestCase
{
    use DiscoverTestHelpers;
    use RefreshDatabase;

    private const LONDON = [-0.1276, 51.5072];

    private const PARIS = [2.3522, 48.8566];

    private const CAIRO = [31.2357, 30.0444];

    private const BEIJING = [116.4074, 39.9042];

    private const NEW_YORK = [-74.0060, 40.7128];

    private const LIMA = [-77.0428, -12.0464];

    private const HONOLULU = [-157.8583, 21.3069];

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
    }

    /**
     * An event on the map at a point, dated by its geometry period.
     *
     * @param  array{0: float, 1: float}  $at
     */
    private function event(string $name, array $at, int $start, ?int $end = null, int $impact = 70, ?int $priority = null, EntityType $type = EntityType::EventBattle): Entity
    {
        $entity = $this->entity($type, $name, $impact, ['display_priority' => $priority]);

        return $this->onMap($entity, $at[0], $at[1], $start, $end ?? $start);
    }

    /**
     * A state on the map; no end year means it still stands.
     *
     * @param  array{0: float, 1: float}  $at
     */
    private function state(string $name, array $at, int $start, ?int $end, int $impact = 70, EntityType $type = EntityType::PoliticalEntity): Entity
    {
        return $this->onMap($this->entity($type, $name, $impact), $at[0], $at[1], $start, $end);
    }

    /** @return array<string, mixed> */
    private function meanwhile(int $year): array
    {
        $this->refreshTiles();

        return $this->getJson("/api/v1/discover/meanwhile?year={$year}")->assertOk()->json('data');
    }

    /** @return array<string, array<string, mixed>> the answer's regions by key */
    private function regions(int $year): array
    {
        return collect($this->meanwhile($year)['regions'])->keyBy('key')->all();
    }

    public function test_each_region_gets_its_event_and_its_state_west_to_east(): void
    {
        $hastings = $this->located($this->event('Battle of Hastings', [0.49, 50.91], 1066, 1066, 92), 0.487654321, 50.912345678);
        $this->dated($hastings, '1066-10-14', '1066-10-14');
        $this->story($hastings, 'battle-of-hastings', 1066);
        $england = $this->dated($this->state('Kingdom of England', self::LONDON, 927, 1707, 98), '0927', '1707');
        $song = $this->state('Song China', self::BEIJING, 960, 1279, 98);
        $manzikert = $this->event('Battle of Manzikert', [42.59, 39.1], 1071, 1071, 92);
        $lenape = $this->state('Lenape', self::NEW_YORK, -1000, null, 96);

        $this->refreshTiles();
        $response = $this->getJson('/api/v1/discover/meanwhile?year=1066')->assertOk();

        $this->assertSame('max-age=300, public', $response->headers->get('Cache-Control'));
        $response->assertExactJson(['data' => [
            'year' => 1066,
            'window' => 10,
            'totals' => ['events' => 2, 'polities' => 3],
            'regions' => [
                [
                    'key' => 'north-america', 'name' => 'North America',
                    'event' => null,
                    'polity' => $this->shape($lenape, -1000, null, self::NEW_YORK),
                    'counts' => ['events' => 0, 'polities' => 1],
                ],
                [
                    'key' => 'europe', 'name' => 'Europe',
                    // Its own dates and its primary point, not the tile's.
                    'event' => $this->shape($hastings, 1066, 1066, [0.48765, 50.91235], true),
                    'polity' => $this->shape($england, 927, 1707, self::LONDON),
                    'counts' => ['events' => 1, 'polities' => 1],
                ],
                [
                    'key' => 'middle-east-north-africa', 'name' => 'Middle East & North Africa',
                    'event' => $this->shape($manzikert, 1071, 1071, [42.59, 39.1]),
                    'polity' => null,
                    'counts' => ['events' => 1, 'polities' => 0],
                ],
                [
                    'key' => 'east-asia', 'name' => 'East Asia',
                    'event' => null,
                    'polity' => $this->shape($song, 960, 1279, self::BEIJING),
                    'counts' => ['events' => 0, 'polities' => 1],
                ],
            ],
        ]]);
    }

    public function test_an_event_counts_within_ten_years_and_a_state_while_it_stands(): void
    {
        $this->event('Ten years before', self::LONDON, 1056);
        $this->event('Eleven years before', self::LONDON, 1055);
        $this->event('Ten years after', self::PARIS, 1076);
        $this->event('Eleven years after', self::PARIS, 1077);
        $this->event('Long war that began earlier', self::PARIS, 1000, 1060);
        $this->event('Long war that ended too early', self::PARIS, 1000, 1055);
        $this->state('Founded that year', self::LONDON, 1066, 1100);
        $this->state('Ended that year', self::LONDON, 900, 1066);
        $this->state('Founded the year after', self::LONDON, 1067, 1100);
        $this->state('Ended the year before', self::LONDON, 900, 1065);
        $this->state('Still standing', self::LONDON, 1000, null);

        $data = $this->meanwhile(1066);

        $this->assertSame(['events' => 3, 'polities' => 3], $data['totals']);
        $this->assertSame(['events' => 3, 'polities' => 3], $data['regions'][0]['counts']);
    }

    public function test_the_event_is_the_most_important_then_the_nearest_in_time(): void
    {
        $this->event('Important but years away', self::LONDON, 1058, 1058, 90);
        $this->event('Minor, that very year', self::LONDON, 1066, 1066, 60);
        $this->assertSame('Important but years away', $this->regions(1066)['europe']['event']['name']);

        Cache::flush();
        $this->event('As important, nearer', self::PARIS, 1069, 1069, 90);
        $this->assertSame('As important, nearer', $this->regions(1066)['europe']['event']['name']);

        Cache::flush();
        $this->event('Raised by a curated priority', self::PARIS, 1060, 1060, 10, 95);
        $this->assertSame('Raised by a curated priority', $this->regions(1066)['europe']['event']['name']);
    }

    public function test_the_state_is_the_most_mentioned_for_its_years_then_the_most_important_then_the_longest_standing(): void
    {
        $this->state('Old but obscure', self::LONDON, 601, 1236, 98);
        $this->state('Younger', self::PARIS, 987, 1848, 98);
        $this->state('Less important', self::PARIS, 500, 1500, 96);
        // Nothing is mentioned: importance, then the longest standing.
        $this->assertSame('Old but obscure', $this->regions(1066)['europe']['polity']['name']);

        // Mentions come before importance: 5 over ten centuries beats 2 over nine.
        Cache::flush();
        $this->mention(Entity::query()->where('name', 'Younger')->sole(), 2);
        $this->mention(Entity::query()->where('name', 'Less important')->sole(), 5);
        $this->assertSame('Less important', $this->regions(1066)['europe']['polity']['name']);

        // They count for the time a state stood: one mention in fifty years is
        // more than five in a thousand.
        Cache::flush();
        $this->mention($this->state('Brief', self::LONDON, 1050, 1100, 60), 1);
        $this->assertSame('Brief', $this->regions(1066)['europe']['polity']['name']);

        // A state that still stands is measured to this year.
        Cache::flush();
        $this->mention($this->state('Still standing', self::PARIS, 1060, null, 60), 3);
        $this->assertSame('Brief', $this->regions(1066)['europe']['polity']['name']);
    }

    public function test_people_are_not_states_and_other_groups_are_not_counted(): void
    {
        $this->state('A king', self::LONDON, 1042, 1066, 99, EntityType::Person);
        $this->state('A city', self::LONDON, 43, null, 99, EntityType::City);
        $this->state('An army', self::PARIS, 1060, 1070, 60, EntityType::MilitaryUnit);
        $this->event('A treaty', self::PARIS, 1066, 1066, 60, null, EntityType::EventTreaty);

        $data = $this->meanwhile(1066);

        $this->assertSame(['events' => 1, 'polities' => 1], $data['totals']);
        $this->assertSame(['An army', 'A treaty'], [$data['regions'][0]['polity']['name'], $data['regions'][0]['event']['name']]);
    }

    public function test_a_feature_outside_every_region_counts_in_the_totals_only(): void
    {
        $this->event('Landing in Hawaii', self::HONOLULU, 1778);
        $this->state('Kingdom in Hawaii', self::HONOLULU, 1700, 1893);
        $this->event('Expedition to the South Pole', [0.0, -90.0], 1778, 1779, 99);
        $this->event('Battle in Peru', self::LIMA, 1780);

        $data = $this->meanwhile(1778);

        $this->assertSame(['events' => 3, 'polities' => 1], $data['totals']);
        $this->assertSame(['south-america'], array_column($data['regions'], 'key'));
        $this->assertSame(['events' => 1, 'polities' => 0], $data['regions'][0]['counts']);
    }

    public function test_an_entity_with_several_periods_counts_once(): void
    {
        $empire = $this->state('Empire of two borders', self::CAIRO, 900, 1050);
        $this->onMap($empire, self::CAIRO[0] + 1, self::CAIRO[1], 1050, 1200);
        $war = $this->event('War on two fronts', self::CAIRO, 1048, 1049);
        $this->onMap($war, self::CAIRO[0] + 2, self::CAIRO[1], 1051, 1052);

        $data = $this->meanwhile(1050);

        $this->assertSame(['events' => 1, 'polities' => 1], $data['totals']);
        $this->assertSame(['events' => 1, 'polities' => 1], $data['regions'][0]['counts']);
    }

    public function test_hidden_entities_are_left_out_and_the_runner_up_stands_in(): void
    {
        $this->state('Rejected state', self::LONDON, 900, 1200, 99, EntityType::PoliticalEntity)
            ->update(['verification_status' => VerificationStatus::Rejected->value]);
        $best = $this->event('Best event', self::LONDON, 1066, 1066, 90);
        $this->event('Runner-up', self::PARIS, 1066, 1066, 80);
        $this->refreshTiles();

        // Flagged after the tile table was refreshed: still a row there.
        DB::table('entities')->where('entity_id', $best->entity_id)->update(['verification_status' => VerificationStatus::Flagged->value]);
        $europe = collect($this->getJson('/api/v1/discover/meanwhile?year=1066')->assertOk()->json('data.regions'))->firstWhere('key', 'europe');

        $this->assertSame('Runner-up', $europe['event']['name']);
        $this->assertNull($europe['polity']);
    }

    public function test_a_year_with_nothing_on_the_map_has_no_regions(): void
    {
        $this->event('Much later', self::LONDON, 1500);

        $this->assertSame(
            ['year' => -3000, 'window' => 10, 'totals' => ['events' => 0, 'polities' => 0], 'regions' => []],
            $this->meanwhile(-3000),
        );
    }

    public function test_the_answer_is_cached_per_year(): void
    {
        $this->event('First', self::LONDON, 1066, 1066, 60);
        $this->assertSame('First', $this->regions(1066)['europe']['event']['name']);

        $this->event('Better, but after the answer was cached', self::LONDON, 1066, 1066, 90);
        $this->assertSame('First', $this->regions(1066)['europe']['event']['name']);
        $this->assertSame('Better, but after the answer was cached', $this->regions(1067)['europe']['event']['name']);
    }

    public function test_the_year_is_required_and_bounded(): void
    {
        Carbon::setTestNow('2026-11-20 12:00:00');

        foreach (['', '?year=', '?year=soon', '?year=1066.5', '?year=-4001', '?year=2027'] as $query) {
            $this->getJson('/api/v1/discover/meanwhile'.$query)->assertStatus(422)->assertJsonValidationErrors('year');
        }
        foreach ([-4000, -1, 0, 2026] as $year) {
            $this->getJson("/api/v1/discover/meanwhile?year={$year}")->assertOk()->assertJsonPath('data.year', $year);
        }
    }

    public function test_the_sql_region_rule_agrees_with_the_php_one(): void
    {
        $points = [];
        for ($lng = -180.0; $lng <= 180.0; $lng += 7.5) {
            for ($lat = -90.0; $lat <= 90.0; $lat += 7.5) {
                $points[] = [$lng, $lat];
            }
        }
        // Every edge of every box, and a hair either side of it.
        foreach ([-170, -130, -120, -93, -58, -50, -30, -25, -20, -18, 26, 45, 52, 60, 63, 92, 93, 110, 141, 150, 180] as $lng) {
            foreach ([-60, -11, -8, 5, 7, 12, 13, 20, 24, 36, 37, 42, 55, 85] as $lat) {
                foreach ([-0.001, 0.0, 0.001] as $dx) {
                    foreach ([-0.001, 0.0, 0.001] as $dy) {
                        $points[] = [$lng + $dx, $lat + $dy];
                    }
                }
            }
        }

        $values = implode(', ', array_map(fn (array $p): string => sprintf('(%.4F::float8, %.4F::float8)', $p[0], $p[1]), $points));
        $rows = DB::select('SELECT p.lng, p.lat, '.WorldRegion::sqlCase('p.lng', 'p.lat')." AS region FROM (VALUES {$values}) AS p(lng, lat)");

        $this->assertCount(count($points), $rows);
        foreach ($rows as $row) {
            $this->assertSame(
                WorldRegion::keyFor((float) $row->lng, (float) $row->lat),
                $row->region,
                "({$row->lng}, {$row->lat})",
            );
        }
    }
}
