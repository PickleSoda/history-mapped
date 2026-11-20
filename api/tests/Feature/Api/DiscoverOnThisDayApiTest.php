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
 * GET /api/v1/discover/on-this-day and the table behind it
 * (`php artisan discover:build-anniversaries`).
 */
class DiscoverOnThisDayApiTest extends TestCase
{
    use DiscoverTestHelpers;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
    }

    private function build(): void
    {
        $this->artisan('discover:build-anniversaries')->assertSuccessful();
    }

    /** @return array<string, array<string, mixed>> the table's rows, keyed "entity name / kind" */
    private function anniversaries(): array
    {
        return DB::table('discover_anniversaries as a')
            ->join('entities as e', 'e.entity_id', '=', 'a.entity_id')
            ->get(['e.name', 'a.kind', 'a.month', 'a.day', 'a.year', 'a.date', 'a.impact', 'a.placed'])
            ->mapWithKeys(fn (object $row): array => ["{$row->name} / {$row->kind}" => (array) $row])
            ->all();
    }

    /** @return array<string, mixed> */
    private function onThisDay(string $date): array
    {
        return $this->getJson("/api/v1/discover/on-this-day?date={$date}")->assertOk()->json('data');
    }

    /**
     * A person from the bulk import: Wikidata timestamps in `attributes` (a
     * list when Wikidata holds several candidate dates).
     *
     * @param  string|list<array<string, mixed>>|null  $born
     */
    private function wikidataPerson(string $name, string|array|null $born, ?string $died, int $impact = 70): Entity
    {
        return $this->entity(EntityType::Person, $name, $impact, [
            'attributes' => array_filter(['birth_date' => $born, 'death_date' => $died], fn (mixed $v): bool => $v !== null),
        ]);
    }

    public function test_date_ranges_become_rows_by_what_the_entity_is(): void
    {
        $this->dated($this->entity(EntityType::EventBattle, 'One-day battle'), '1845-11-20', '1845-11-20');
        $this->dated($this->entity(EntityType::EventTreaty, 'Treaty with no end'), '1815-11-20');
        $this->dated($this->entity(EntityType::EventBattle, 'Two-week siege'), '1979-11-20', '1979-12-04');
        $this->dated($this->entity(EntityType::EventWar, 'War with a loose end'), '1962-09-26', '1970');
        $this->dated($this->entity(EntityType::EventBattle, 'Siege with a loose start'), '1601', '1604-09-22');
        $this->dated($this->entity(EntityType::MilitaryUnit, 'An army'), '1861-11-20', '1865-06-28');
        $this->dated($this->entity(EntityType::City, 'Rome'), '-0753-04-21');
        $this->dated($this->entity(EntityType::Person, 'A general'), '1603-11-20', '1667-10-18');
        $this->dated($this->entity(EntityType::LegalCode, 'A law enacted on a day'), '1215-06-15', '1215-06-15');

        $this->build();

        $rows = $this->anniversaries();
        $this->assertSame([
            'A general / born', 'A general / died', 'A law enacted on a day / founded', 'An army / dissolved', 'An army / founded', 'One-day battle / happened',
            'Rome / founded', 'Siege with a loose start / ended', 'Treaty with no end / happened', 'Two-week siege / began',
            'Two-week siege / ended', 'War with a loose end / began',
        ], collect($rows)->keys()->sort()->values()->all());

        $this->assertSame(
            ['name' => 'Rome', 'kind' => 'founded', 'month' => 4, 'day' => 21, 'year' => -753, 'date' => '-0753-04-21', 'impact' => 70, 'placed' => false],
            $rows['Rome / founded'],
        );
        $this->assertSame([12, 4, 1979], [$rows['Two-week siege / ended']['month'], $rows['Two-week siege / ended']['day'], $rows['Two-week siege / ended']['year']]);
        $this->assertSame('1604-09-22', $rows['Siege with a loose start / ended']['date']);
    }

    public function test_placeholders_and_dates_without_a_real_day_are_left_out(): void
    {
        $this->dated($this->entity(EntityType::EventWar, 'Year only'), '1914', '1918');
        $this->dated($this->entity(EntityType::EventWar, 'Month only'), '1791-08', '1804-01');
        $this->dated($this->entity(EntityType::EventWar, 'Whole-year placeholders'), '1939-01-01', '1945-12-31');
        $this->dated($this->entity(EntityType::EventWar, 'Ends on new year'), '1804-01-01', '1805-01-01');
        $this->dated($this->entity(EntityType::Person, 'Day zero'), '1281-02-06', '1362-03-00');
        $this->dated($this->entity(EntityType::EventBattle, 'Month thirteen'), '1500-13-05', '1500-13-05');
        $this->dated($this->entity(EntityType::EventBattle, 'Thirtieth of February'), '1500-02-30', '1500-02-30');
        $this->dated($this->entity(EntityType::EventBattle, 'Leap day'), '1704-02-29', '1704-02-29');

        $this->build();

        $this->assertSame(
            ['Day zero / born', 'Leap day / happened'],
            collect($this->anniversaries())->keys()->sort()->values()->all(),
        );
    }

    public function test_people_come_from_wikidata_timestamps_at_or_above_the_impact_bar(): void
    {
        $this->wikidataPerson('Notable', '1925-11-20T00:00:00Z', '1968-06-06T00:00:00Z', 60);
        $this->wikidataPerson('Below the bar', '1925-11-20T00:00:00Z', '1968-06-06T00:00:00Z', 59);
        $this->wikidataPerson('Year-only dates', '1850-01-01T00:00:00Z', '1910-01-01T00:00:00Z');
        $this->wikidataPerson('Death known to the day', '1800-01-01T00:00:00Z', '1870-05-04T00:00:00Z');
        $this->wikidataPerson('Ovid', '-0042-03-20T00:00:00Z', '0017-01-01T00:00:00Z');
        $this->wikidataPerson('Born in year zero', '0000-06-15T00:00:00Z', '0060-11-30T00:00:00Z');
        $this->wikidataPerson('Two candidate dates', [
            ['label' => '1300-05-02T00:00:00Z', 'wikidata_id' => null],
            ['label' => '1301-05-02T00:00:00Z', 'wikidata_id' => null],
        ], '1360-07-09T00:00:00Z');
        $this->wikidataPerson('Plain date', '1133-03-05', '1189-07-06');

        $this->build();

        $rows = $this->anniversaries();
        $this->assertSame([
            'Born in year zero / born', 'Born in year zero / died', 'Death known to the day / died', 'Notable / born', 'Notable / died',
            'Ovid / born', 'Plain date / born', 'Plain date / died', 'Two candidate dates / died',
        ], collect($rows)->keys()->sort()->values()->all());

        // Wikidata numbers years astronomically: -0042 is 43 BCE, 0000 is 1 BCE.
        $this->assertSame([-43, '-0043-03-20', 3, 20], [$rows['Ovid / born']['year'], $rows['Ovid / born']['date'], $rows['Ovid / born']['month'], $rows['Ovid / born']['day']]);
        $this->assertSame([-1, '-0001-06-15'], [$rows['Born in year zero / born']['year'], $rows['Born in year zero / born']['date']]);
        $this->assertSame([1925, '1925-11-20', 60], [$rows['Notable / born']['year'], $rows['Notable / born']['date'], $rows['Notable / born']['impact']]);
        $this->assertSame([1133, '1133-03-05'], [$rows['Plain date / born']['year'], $rows['Plain date / born']['date']]);
    }

    public function test_only_people_known_to_have_died_get_a_birthday(): void
    {
        $this->wikidataPerson('Living, from Wikidata', '1942-11-20T00:00:00Z', null, 80);
        $this->wikidataPerson('Died at an unknown time', '0417-11-20T00:00:00Z', 'http://www.wikidata.org/.well-known/genid/15f8470aa06c91cb');
        $this->dated($this->entity(EntityType::Person, 'Living, from a campaign'), '1955-10-28');
        $this->dated($this->entity(EntityType::Person, 'Died in a known year'), '0877-01-31', '943');

        $this->build();

        $this->assertSame(
            ['Died at an unknown time / born', 'Died in a known year / born'],
            collect($this->anniversaries())->keys()->sort()->values()->all(),
        );
    }

    public function test_a_date_range_row_wins_over_the_attributes_and_hidden_entities_are_left_out(): void
    {
        $both = $this->wikidataPerson('In both sources', '1810-03-01T00:00:00Z', '1849-10-17T00:00:00Z');
        $this->dated($both, '1810-02-22', '1849-10-17');
        $merged = $this->wikidataPerson('Merged away', '1810-03-01T00:00:00Z', '1849-10-17T00:00:00Z');
        $merged->update(['verification_status' => VerificationStatus::Merged->value]);
        $this->dated($this->entity(EntityType::EventBattle, 'Rejected battle', 70, ['verification_status' => VerificationStatus::Rejected->value]), '1845-11-20', '1845-11-20');

        $this->build();

        $rows = $this->anniversaries();
        $this->assertSame(['In both sources / born', 'In both sources / died'], collect($rows)->keys()->sort()->values()->all());
        $this->assertSame('1810-02-22', $rows['In both sources / born']['date']);
    }

    public function test_a_date_on_the_first_of_a_month_needs_the_summary_to_state_it(): void
    {
        $people = [
            'Month known, day not' => ['1929-06-12T00:00:00Z', '1945-02-01T00:00:00Z', 'Annelies Frank (12 June 1929 – c. February or March 1945) was a diarist.'],
            'Day first' => ['1810-03-01T00:00:00Z', '1849-10-17T00:00:00Z', 'Frédéric Chopin (born Fryderyk Chopin; 1 March 1810 – 17 October 1849) was a composer.'],
            'Month first' => ['1880-06-27T00:00:00Z', '1968-06-01T00:00:00Z', 'Helen Keller (June 27, 1880 – June 1, 1968) was an American author.'],
            'Old style in between' => ['1873-04-01T00:00:00Z', '1943-03-28T00:00:00Z', 'Sergei Rachmaninoff (1 April [O.S. 20 March] 1873 – 28 March 1943) was a composer.'],
            'Before the common era' => ['-0085-10-01T00:00:00Z', '-0034-05-13T00:00:00Z', 'Sallust (1 October 86 BC – 13 May 35 BC) was a Roman historian.'],
            'Another year' => ['1852-08-30T00:00:00Z', '1901-03-01T00:00:00Z', 'Jacobus van \'t Hoff (30 August 1852 – 1 March 1911) was a chemist.'],
            'The eleventh, not the first' => ['1800-05-01T00:00:00Z', '1870-02-02T00:00:00Z', 'A painter (11 May 1800 – 2 February 1870).'],
            'No summary' => ['1700-09-01T00:00:00Z', '1770-02-02T00:00:00Z', null],
        ];
        foreach ($people as $name => [$born, $died, $summary]) {
            $this->wikidataPerson($name, $born, $died)->update(['summary' => $summary]);
        }
        // The same rule for the date ranges.
        $this->dated($this->entity(EntityType::PoliticalEntity, 'Union stated', 70, ['summary' => 'Formed on 1 December 1918 from three kingdoms.']), '1918-12-01', '1992-04-27');
        $this->dated($this->entity(EntityType::PoliticalEntity, 'Kingdom not stated', 70, ['summary' => 'Founded in 1795 after a long war.']), '1795-05-01', '1893-01-17');
        $firsts = fn (): array => collect($this->anniversaries())->where('day', 1)->keys()->sort()->values()->all();

        $this->build();
        $this->assertSame(
            ['Before the common era / born', 'Day first / born', 'Month first / died', 'Old style in between / born', 'Union stated / founded'],
            $firsts(),
        );
        // The other dates of the same entities stay.
        $this->assertArrayHasKey('Month known, day not / born', $this->anniversaries());
        $this->assertArrayHasKey('Kingdom not stated / dissolved', $this->anniversaries());

        config(['discover.anniversaries.first_of_month' => 'none']);
        $this->build();
        $this->assertSame([], $firsts());

        config(['discover.anniversaries.first_of_month' => 'all']);
        $this->build();
        $this->assertCount(10, $firsts());
    }

    public function test_a_day_lists_placed_entities_first_then_by_impact(): void
    {
        $battle = $this->located($this->dated($this->entity(EntityType::EventBattle, 'Placed battle', 62), '1845-11-20', '1845-11-20'), -59.807224, -33.59222);
        $onMap = $this->onMap($this->dated($this->entity(EntityType::City, 'City with a border only', 55), '1200-11-20'), 12.5, 41.9, 1200);
        $treaty = $this->dated($this->entity(EntityType::EventTreaty, 'Unplaced treaty', 90), '1815-11-20', '1815-11-20');
        $person = $this->wikidataPerson('Unplaced writer', '1858-11-20T00:00:00Z', '1940-03-16T00:00:00Z', 80);
        $this->dated($this->entity(EntityType::EventBattle, 'Another day'), '1845-11-21', '1845-11-21');
        $this->story($battle, 'placed-battle');
        $this->build();

        $response = $this->getJson('/api/v1/discover/on-this-day?date=2026-11-20')->assertOk();

        $this->assertSame('max-age=300, public', $response->headers->get('Cache-Control'));
        $response->assertExactJson(['data' => [
            'month' => 11,
            'day' => 20,
            'widened' => 0,
            'items' => [
                [...$this->shape($battle, 1845, 1845, [-59.80722, -33.59222], true), 'kind' => 'happened', 'year' => 1845, 'date' => '1845-11-20'],
                [...$this->shape($onMap, 1200, null, [12.5, 41.9]), 'kind' => 'founded', 'year' => 1200, 'date' => '1200-11-20'],
                [...$this->shape($treaty, 1815, 1815, null), 'kind' => 'happened', 'year' => 1815, 'date' => '1815-11-20'],
                [...$this->shape($person, null, null, null), 'kind' => 'born', 'year' => 1858, 'date' => '1858-11-20'],
            ],
        ]]);
    }

    public function test_only_the_month_and_day_of_the_date_matter_and_the_default_is_the_utc_day(): void
    {
        $this->dated($this->entity(EntityType::EventBattle, 'Hastings', 90), '1066-10-14', '1066-10-14');
        foreach (['First', 'Second', 'Third'] as $i => $name) {
            $this->dated($this->entity(EntityType::EventBattle, $name, 80 - $i), '1700-10-14', '1700-10-14');
        }
        $this->build();

        $this->assertSame(['Hastings', 'First', 'Second', 'Third'], array_column($this->onThisDay('1999-10-14')['items'], 'name'));

        Carbon::setTestNow('2026-10-14 23:30:00');
        $data = $this->getJson('/api/v1/discover/on-this-day')->assertOk()->json('data');
        $this->assertSame([10, 14, 0, 4], [$data['month'], $data['day'], $data['widened'], count($data['items'])]);
    }

    public function test_people_take_at_most_four_places_and_leave_two_for_the_rest(): void
    {
        foreach (range(1, 6) as $i) {
            $this->wikidataPerson("Person {$i}", "18{$i}0-07-04T00:00:00Z", '1900-01-01T00:00:00Z', 100 - $i);
        }
        foreach (range(1, 9) as $i) {
            $this->dated($this->entity(EntityType::EventBattle, "Battle {$i}", 60 - $i), "17{$i}0-07-04", "17{$i}0-07-04");
        }
        $this->build();

        $names = array_column($this->onThisDay('2026-07-04')['items'], 'name');

        // Eight in all: the four best people (the higher impact, so first), then battles.
        $this->assertSame(
            ['Person 1', 'Person 2', 'Person 3', 'Person 4', 'Battle 1', 'Battle 2', 'Battle 3', 'Battle 4'],
            $names,
        );
    }

    public function test_a_smaller_answer_still_keeps_two_places_for_the_other_kinds(): void
    {
        config(['discover.on_this_day.size' => 5]);
        foreach (range(1, 6) as $i) {
            $this->wikidataPerson("Person {$i}", "18{$i}0-07-04T00:00:00Z", '1900-01-01T00:00:00Z', 100 - $i);
        }
        foreach (range(1, 3) as $i) {
            $this->dated($this->entity(EntityType::EventBattle, "Battle {$i}", 60 - $i), "17{$i}0-07-04", "17{$i}0-07-04");
        }
        $this->build();

        $this->assertSame(
            ['Person 1', 'Person 2', 'Person 3', 'Battle 1', 'Battle 2'],
            array_column($this->onThisDay('2026-07-04')['items'], 'name'),
        );
    }

    public function test_an_entity_with_two_rows_on_one_day_is_listed_once(): void
    {
        $this->dated($this->entity(EntityType::EventWar, 'Seven years to the day', 90), '1756-05-17', '1763-05-17');
        $this->dated($this->entity(EntityType::EventBattle, 'Filler A', 50), '1800-05-17', '1800-05-17');
        $this->dated($this->entity(EntityType::EventBattle, 'Filler B', 49), '1801-05-17', '1801-05-17');
        $this->dated($this->entity(EntityType::EventBattle, 'Filler C', 48), '1802-05-17', '1802-05-17');
        $this->build();

        $items = $this->onThisDay('2026-05-17')['items'];

        $this->assertSame(['Seven years to the day', 'Filler A', 'Filler B', 'Filler C'], array_column($items, 'name'));
        $this->assertSame(['began', 1756], [$items[0]['kind'], $items[0]['year']]);
    }

    public function test_a_thin_day_borrows_from_its_neighbours_until_it_has_four(): void
    {
        $this->dated($this->entity(EntityType::EventBattle, 'On the day', 50), '1500-06-10', '1500-06-10');
        $this->dated($this->entity(EntityType::EventBattle, 'Day before', 60), '1500-06-09', '1500-06-09');
        $this->dated($this->entity(EntityType::EventBattle, 'Day after', 70), '1500-06-11', '1500-06-11');
        $this->dated($this->entity(EntityType::EventBattle, 'Two days before, minor', 40), '1500-06-08', '1500-06-08');
        $this->dated($this->entity(EntityType::EventBattle, 'Two days after, major', 90), '1500-06-12', '1500-06-12');
        $this->dated($this->entity(EntityType::EventBattle, 'Three days after', 99), '1500-06-13', '1500-06-13');
        $this->build();

        $data = $this->onThisDay('2026-06-10');

        // Its own first, then the nearest days, best first; it stops at four.
        $this->assertSame(2, $data['widened']);
        $this->assertSame(['On the day', 'Day after', 'Day before', 'Two days after, major'], array_column($data['items'], 'name'));
        $this->assertSame(['1500-06-10', '1500-06-11', '1500-06-09', '1500-06-12'], array_column($data['items'], 'date'));
    }

    public function test_neighbouring_days_wrap_around_the_year_and_know_the_leap_day(): void
    {
        $this->dated($this->entity(EntityType::EventBattle, 'New year eve', 50), '1500-12-31', '1500-12-31');
        $this->dated($this->entity(EntityType::EventBattle, 'Second of January', 60), '1500-01-02', '1500-01-02');
        $this->dated($this->entity(EntityType::EventBattle, 'Leap day', 50), '1704-02-29', '1704-02-29');
        $this->dated($this->entity(EntityType::EventBattle, 'End of February', 60), '1704-02-28', '1704-02-28');
        $this->build();

        $newYear = $this->onThisDay('2026-01-01');
        $this->assertSame(['Second of January', 'New year eve'], array_column($newYear['items'], 'name'));
        $this->assertSame(3, $newYear['widened']);

        $this->assertSame(['Leap day', 'End of February'], array_column($this->onThisDay('2024-03-01')['items'], 'name'));
        $this->assertSame(['Leap day', 'End of February'], array_column($this->onThisDay('2024-02-29')['items'], 'name'));
    }

    public function test_the_build_can_be_asked_to_run_only_when_the_table_is_empty(): void
    {
        $this->dated($this->entity(EntityType::EventBattle, 'Battle of Waterloo', 92), '1815-06-18', '1815-06-18');

        // Empty: it builds.
        $this->artisan('discover:build-anniversaries --if-empty')->assertSuccessful();
        $this->assertSame(1, DB::table('discover_anniversaries')->count());

        // Not empty: it leaves the table as it is, whatever has changed since.
        $this->dated($this->entity(EntityType::EventBattle, 'Battle of Ligny', 80), '1815-06-16', '1815-06-16');
        $this->artisan('discover:build-anniversaries --if-empty')
            ->expectsOutputToContain('already built')
            ->assertSuccessful();
        $this->assertSame(1, DB::table('discover_anniversaries')->count());

        // Without the option it always rebuilds.
        $this->build();
        $this->assertSame(2, DB::table('discover_anniversaries')->count());
    }

    public function test_an_empty_table_gives_an_empty_list(): void
    {
        $this->getJson('/api/v1/discover/on-this-day?date=2026-11-20')
            ->assertOk()
            ->assertExactJson(['data' => ['month' => 11, 'day' => 20, 'widened' => 3, 'items' => []]]);
    }

    public function test_the_answer_is_cached_until_the_table_is_rebuilt(): void
    {
        $known = $this->dated($this->entity(EntityType::EventBattle, 'Known', 50), '1500-08-08', '1500-08-08');
        foreach (range(1, 3) as $i) {
            $this->dated($this->entity(EntityType::EventBattle, "Filler {$i}", 40 - $i), "160{$i}-08-08", "160{$i}-08-08");
        }
        $this->build();
        $this->assertSame(['Known', 'Filler 1', 'Filler 2', 'Filler 3'], array_column($this->onThisDay('2026-08-08')['items'], 'name'));

        // A change the cached answer does not see…
        DB::table('entities')->where('entity_id', $known->entity_id)->update(['name' => 'Renamed']);
        $late = $this->dated($this->entity(EntityType::EventBattle, 'Added later', 99), '1700-08-08', '1700-08-08');
        $this->assertSame(['Known', 'Filler 1', 'Filler 2', 'Filler 3'], array_column($this->onThisDay('2026-08-08')['items'], 'name'));

        // …until the build forgets the cached days.
        $this->build();
        $this->assertSame(['Added later', 'Renamed', 'Filler 1', 'Filler 2', 'Filler 3'], array_column($this->onThisDay('2026-08-08')['items'], 'name'));

        // A deleted entity takes its rows with it.
        $late->delete();
        $this->assertDatabaseMissing('discover_anniversaries', ['entity_id' => $late->entity_id]);
    }

    public function test_an_entity_hidden_since_the_build_is_not_shown(): void
    {
        $shown = $this->dated($this->entity(EntityType::EventBattle, 'Shown', 50), '1500-09-09', '1500-09-09');
        $hidden = $this->dated($this->entity(EntityType::EventBattle, 'Flagged afterwards', 90), '1501-09-09', '1501-09-09');
        $this->build();
        $hidden->update(['verification_status' => VerificationStatus::Flagged->value]);

        $this->assertSame([$shown->entity_id], array_column($this->onThisDay('2026-09-09')['items'], 'id'));
    }

    public function test_a_date_that_is_not_a_day_is_refused(): void
    {
        foreach (['today', '2026-13-01', '2026-02-30', '20-11-2026', '2026-11-20T10:00:00Z'] as $date) {
            $this->getJson('/api/v1/discover/on-this-day?date='.urlencode($date))
                ->assertStatus(422)
                ->assertJsonValidationErrors('date');
        }
    }
}
