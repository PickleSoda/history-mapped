<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * GET /api/v1/discover/quest: the day's three battles to find, one per
 * difficulty, the same for everyone on a date.
 */
class DiscoverQuestApiTest extends TestCase
{
    use DiscoverTestHelpers;
    use RefreshDatabase;

    private const TODAY = '2026-11-20';

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
        Carbon::setTestNow(self::TODAY.' 09:00:00');
    }

    /**
     * A battle the tiles show from zoom 3 (importance 80 and up), in Europe
     * unless placed elsewhere.
     *
     * @param  array<string, mixed>  $state
     */
    private function battle(string $name, int $year = 1500, float $lng = 2.35, float $lat = 48.85, int $impact = 85, array $state = []): Entity
    {
        return $this->onMap($this->entity(EntityType::EventBattle, $name, $impact, $state), $lng, $lat, $year, $year);
    }

    /** One battle of each difficulty: mentioned twice, once, never. */
    private function oneOfEach(): array
    {
        $easy = $this->battle('Easy battle');
        $this->mention($easy, 2);
        $medium = $this->battle('Medium battle');
        $this->mention($medium);
        $hard = $this->battle('Hard battle');

        return [$easy, $medium, $hard];
    }

    /** @return array<string, mixed> */
    private function quest(?string $date = null): array
    {
        $this->refreshTiles();

        return $this->getJson('/api/v1/discover/quest'.($date === null ? '' : "?date={$date}"))->assertOk()->json('data');
    }

    /** @param list<Entity> $battles */
    private function firstByHash(array $battles, string $date): string
    {
        return collect($battles)->sortBy(fn (Entity $battle): string => md5($battle->entity_id.$date), SORT_STRING)->first()->name;
    }

    public function test_the_day_has_one_target_of_each_difficulty_in_order(): void
    {
        $easy = $this->located($this->battle('Battle of Hastings', 1066, 0.49, 50.91), 0.487654, 50.912346, 'Senlac Hill, East Sussex');
        $this->dated($easy, '1066-10-14', '1066-10-14');
        $this->mention($easy, 2);
        $medium = $this->battle('Battle of Magdala', 1868, 39.18, 11.35);
        $this->mention($medium);
        $hard = $this->battle('Siege of Jhain', 1291, 76.48, 25.89);
        $this->refreshTiles();

        $response = $this->getJson('/api/v1/discover/quest?date='.self::TODAY)->assertOk();

        $this->assertSame('max-age=300, public', $response->headers->get('Cache-Control'));
        $response->assertExactJson(['data' => [
            'date' => self::TODAY,
            'number' => 1,
            'targets' => [
                [...$this->shape($easy, 1066, 1066, [0.48765, 50.91235]), 'difficulty' => 'easy', 'year' => 1066, 'region' => 'Europe', 'place' => 'Senlac Hill, East Sussex'],
                [...$this->shape($medium, 1868, 1868, [39.18, 11.35]), 'difficulty' => 'medium', 'year' => 1868, 'region' => 'Sub-Saharan Africa', 'place' => null],
                [...$this->shape($hard, 1291, 1291, [76.48, 25.89]), 'difficulty' => 'hard', 'year' => 1291, 'region' => 'South Asia', 'place' => null],
            ],
        ]]);
    }

    public function test_a_battle_map_makes_a_battle_easy_and_mentions_decide_the_rest(): void
    {
        $withMap = $this->battle('Never mentioned, but mapped');
        $this->story($withMap, 'never-mentioned-but-mapped', 1500);
        $once = $this->battle('Mentioned once');
        $this->mention($once);
        $never = $this->battle('Never mentioned');

        $targets = collect($this->quest()['targets'])->pluck('name', 'difficulty')->all();

        $this->assertSame(['easy' => 'Never mentioned, but mapped', 'medium' => 'Mentioned once', 'hard' => 'Never mentioned'], $targets);
        $this->assertTrue($this->quest()['targets'][0]['has_map_story']);
    }

    public function test_within_a_tier_the_date_decides_and_everyone_gets_the_same(): void
    {
        $battles = array_map(fn (int $i): Entity => $this->battle("Unsung battle {$i}", 1400 + $i), range(1, 12));

        foreach (['2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22'] as $date) {
            $data = $this->quest($date);
            // Only never-mentioned battles: a single, hard target, the first by md5(id || date).
            $this->assertSame(['hard'], array_column($data['targets'], 'difficulty'));
            $this->assertSame($this->firstByHash($battles, $date), $data['targets'][0]['name'], $date);
        }
    }

    public function test_the_pool_is_battles_shown_from_zoom_three_in_a_region_with_a_clue(): void
    {
        $this->battle('In the pool');
        $this->battle('Too minor for zoom three', 1500, 2.35, 48.85, 79);
        $this->battle('In no region', 1500, -157.86, 21.31);
        $this->battle('At the South Pole', 1500, 139.27, -90.0);
        $this->battle('No clue', 1500, 2.35, 48.85, 85, ['summary' => 'Too short.']);
        $this->battle('No summary at all', 1500, 2.35, 48.85, 85, ['summary' => null]);
        $this->battle('Rejected', 1500, 2.35, 48.85, 85, ['verification_status' => VerificationStatus::Rejected->value]);
        $this->onMap($this->entity(EntityType::EventWar, 'A war, not a battle', 95), 2.35, 48.85, 1500, 1500);
        $this->onMap($this->entity(EntityType::City, 'A city', 95), 2.35, 48.85, 1500, null);

        foreach (['2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22'] as $date) {
            $this->assertSame(['In the pool'], array_column($this->quest($date)['targets'], 'name'), $date);
        }
    }

    public function test_a_curated_priority_can_bring_a_minor_battle_into_the_pool(): void
    {
        $this->battle('Minor, but curated', 1500, 2.35, 48.85, 20, ['display_priority' => 80]);

        $this->assertSame(['Minor, but curated'], array_column($this->quest()['targets'], 'name'));
    }

    public function test_when_the_first_few_of_a_tier_have_no_clue_the_whole_tier_is_searched(): void
    {
        foreach (range(1, 14) as $i) {
            $this->battle("Clueless {$i}", 1500, 2.35, 48.85, 85, ['summary' => null]);
        }
        $this->battle('The one with a clue');

        foreach (['2026-11-19', '2026-11-20', '2026-11-21'] as $date) {
            $this->assertSame(['The one with a clue'], array_column($this->quest($date)['targets'], 'name'), $date);
        }
    }

    public function test_a_target_hidden_since_the_tiles_were_refreshed_gives_way_to_the_next(): void
    {
        $battles = array_map(fn (int $i): Entity => $this->battle("Unsung battle {$i}", 1400 + $i), range(1, 6));
        $this->refreshTiles();
        $ranked = collect($battles)->sortBy(fn (Entity $battle): string => md5($battle->entity_id.self::TODAY), SORT_STRING)->values();
        DB::table('entities')->where('entity_id', $ranked[0]->entity_id)->update(['verification_status' => VerificationStatus::Flagged->value]);

        $targets = $this->getJson('/api/v1/discover/quest?date='.self::TODAY)->assertOk()->json('data.targets');

        $this->assertSame([$ranked[1]->name], array_column($targets, 'name'));
    }

    public function test_the_year_is_the_one_the_tiles_show_it_from_and_the_point_is_never_missing(): void
    {
        $undated = $this->battle('Dated only on the map', 1415, 2.14, 50.46);
        $twice = $this->battle('Fought twice', 1643, 4.52, 49.92);
        $this->mention($twice);
        $this->onMap($twice, 4.6, 49.9, 1650, 1651);
        $this->dated($twice, '1640', '1651');

        $targets = collect($this->quest()['targets'])->keyBy('name');

        $this->assertSame([1415, 1415, 1415, [2.14, 50.46]], [
            $targets['Dated only on the map']['year'], $targets['Dated only on the map']['start_year'],
            $targets['Dated only on the map']['end_year'], $targets['Dated only on the map']['at'],
        ]);
        // Its own dates in the entity; the earliest period's year to be in.
        $this->assertSame([1643, 1640, 1651, [4.52, 49.92]], [
            $targets['Fought twice']['year'], $targets['Fought twice']['start_year'],
            $targets['Fought twice']['end_year'], $targets['Fought twice']['at'],
        ]);
        $this->assertSame($undated->entity_id, $targets['Dated only on the map']['id']);
    }

    public function test_the_place_is_a_name_that_says_more_than_the_battles_own(): void
    {
        $named = $this->located($this->battle('Battle of Cannae', -216, 16.13, 41.3), 16.13, 41.3, 'Plain below Canne della Battaglia');
        $this->mention($named, 2);

        $selfNamed = $this->located($this->battle('Siege of Mantua', 1796, 10.79, 45.16), 10.79, 45.16, 'Siege of Mantua');
        $this->mention($selfNamed);
        $mantua = $this->entity(EntityType::City, 'Mantua', 90);
        $italy = $this->entity(EntityType::PoliticalEntity, 'Cisalpine Republic', 60);
        $hidden = $this->entity(EntityType::City, 'Lombard plain', 99, ['verification_status' => VerificationStatus::Merged->value]);
        $this->link($selfNamed, 'located_at', $mantua);
        $this->link($selfNamed, 'located_at', $italy);
        $this->link($selfNamed, 'located_at', $hidden);
        $this->link($selfNamed, 'part_of', $this->entity(EntityType::EventWar, 'War of the First Coalition', 99));

        $this->located($this->battle('Battle of Mantinea (362 BCE)', -362, 22.39, 37.62), 22.39, 37.62, 'Battle of Mantinea');

        $places = collect($this->quest()['targets'])->pluck('place', 'name')->all();

        $this->assertSame([
            'Battle of Cannae' => 'Plain below Canne della Battaglia',
            // "Mantua" is already in its name; the hidden place is not offered.
            'Siege of Mantua' => 'Cisalpine Republic',
            'Battle of Mantinea (362 BCE)' => null,
        ], $places);
    }

    public function test_a_city_is_a_nearer_place_than_a_country(): void
    {
        $battle = $this->battle('Operation Dynamo', 1940, 2.38, 51.03);
        $this->link($battle, 'located_at', $this->entity(EntityType::PoliticalEntity, 'France', 98));
        $this->link($battle, 'located_at', $this->entity(EntityType::City, 'Dunkirk', 60));

        $this->assertSame('Dunkirk', $this->quest()['targets'][0]['place']);
    }

    public function test_expeditions_are_numbered_from_the_first_day(): void
    {
        $this->oneOfEach();

        $this->assertSame([self::TODAY, 1], [$this->quest()['date'], $this->quest()['number']]);
        $this->assertSame(2, $this->quest('2026-11-21')['number']);
        $this->assertSame(0, $this->quest('2026-11-19')['number']);

        config(['discover.quest_epoch' => '2026-01-01']);
        $this->assertSame(326, $this->quest('2026-11-22')['number']);
    }

    public function test_the_date_must_be_a_day_within_two_days_of_today(): void
    {
        $this->oneOfEach();
        $this->refreshTiles();

        foreach (['2026-11-18', '2026-11-22'] as $date) {
            $this->getJson("/api/v1/discover/quest?date={$date}")->assertOk()->assertJsonPath('data.date', $date);
        }
        foreach (['2026-11-17', '2026-11-23', '2025-11-20', 'tomorrow', '2026-11-31'] as $date) {
            $this->getJson("/api/v1/discover/quest?date={$date}")->assertStatus(422)->assertJsonValidationErrors('date');
        }
    }

    public function test_a_days_expedition_is_cached_once_it_is_complete(): void
    {
        [$easy, $medium, $hard] = $this->oneOfEach();
        $first = $this->quest();
        $this->assertSame(['Easy battle', 'Medium battle', 'Hard battle'], array_column($first['targets'], 'name'));

        // The world changes; the day's expedition does not.
        DB::table('entities')->whereIn('entity_id', [$easy->entity_id, $medium->entity_id, $hard->entity_id])
            ->update(['verification_status' => VerificationStatus::Rejected->value]);
        $this->battle('A newcomer');

        $this->assertSame($first, $this->quest());
        $this->assertSame(['A newcomer'], array_column($this->quest('2026-11-21')['targets'], 'name'));
    }

    public function test_an_incomplete_expedition_is_not_kept_for_the_day(): void
    {
        $this->battle('Alone');
        $this->assertSame(['hard'], array_column($this->quest()['targets'], 'difficulty'));

        $this->mention($this->battle('Joined later'));
        $this->travel(6)->minutes();

        $this->assertSame(['medium', 'hard'], array_column($this->quest()['targets'], 'difficulty'));
    }

    public function test_an_empty_map_gives_an_expedition_with_no_targets(): void
    {
        $this->getJson('/api/v1/discover/quest?date='.self::TODAY)
            ->assertOk()
            ->assertExactJson(['data' => ['date' => self::TODAY, 'number' => 1, 'targets' => []]]);
    }
}
