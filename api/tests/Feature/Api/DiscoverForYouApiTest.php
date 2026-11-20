<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * GET /api/v1/discover/for-you: suggestions from the entities a browser
 * opened lately (the seeds, most recent first).
 */
class DiscoverForYouApiTest extends TestCase
{
    use DiscoverTestHelpers;
    use RefreshDatabase;

    /** @param list<Entity|string> $seeds */
    private function forYou(array $seeds): array
    {
        $ids = array_map(fn (Entity|string $seed): string => $seed instanceof Entity ? $seed->entity_id : $seed, $seeds);

        return $this->getJson('/api/v1/discover/for-you?ids='.implode(',', $ids))->assertOk()->json('data');
    }

    /** @param list<array<string, mixed>> $rows */
    private function names(array $rows): array
    {
        return array_column($rows, 'name');
    }

    public function test_it_suggests_the_other_ends_of_a_seeds_relationships(): void
    {
        $hannibal = $this->entity(EntityType::Person, 'Hannibal');
        $cannae = $this->located($this->dated($this->entity(EntityType::EventBattle, 'Battle of Cannae', 92), '-0216-08-02', '-0216-08-02'), 16.13, 41.3);
        $this->story($cannae, 'battle-of-cannae', -216);
        $carthage = $this->entity(EntityType::PoliticalEntity, 'Carthage', 98);
        $this->link($hannibal, 'victorious_at', $cannae);
        $this->link($carthage, 'commanded_by', $hannibal);

        $response = $this->getJson('/api/v1/discover/for-you?ids='.$hannibal->entity_id)->assertOk();

        $this->assertSame('max-age=60, private', $response->headers->get('Cache-Control'));
        $response->assertJsonPath('data.because', [['id' => $hannibal->entity_id, 'name' => 'Hannibal']]);
        $response->assertJsonPath('data.entities', [
            // "Carthage, commanded by, Hannibal": the seed is the target. Carthage has no years to open at.
            [...$this->shape($carthage, null, null, null), 'via' => $hannibal->entity_id, 'relation' => 'commanded_by', 'outgoing' => false, 'year' => null],
            // "Hannibal, victorious at, Cannae": the seed is the source.
            [...$this->shape($cannae, -216, -216, [16.13, 41.3], true), 'via' => $hannibal->entity_id, 'relation' => 'victorious_at', 'outgoing' => true, 'year' => -216],
        ]);
        $response->assertJsonPath('data.chronicles', []);
        $response->assertJsonPath('data.stories.0.slug', 'battle-of-cannae');
        $response->assertJsonPath('data.stories.0.via', $hannibal->entity_id);
    }

    public function test_an_entity_opens_in_the_year_of_its_relationship_or_the_first_year_both_existed(): void
    {
        $battle = $this->dated($this->entity(EntityType::EventBattle, 'Battle of Magdala', 92), '1868-04-13', '1868-04-13');
        $britain = $this->dated($this->entity(EntityType::PoliticalEntity, 'Britain', 98), '1801');
        $napier = $this->dated($this->entity(EntityType::Person, 'Robert Napier', 80), '1810', '1890');
        $later = $this->dated($this->entity(EntityType::PoliticalEntity, 'Founded later', 60), '1900', '1950');
        $dated = $this->dated($this->entity(EntityType::PoliticalEntity, 'With a dated link', 50), '1500', '1700');
        $undated = $this->entity(EntityType::City, 'Magdala', 40);
        $this->link($britain, 'victorious_at', $battle);
        $this->link($battle, 'commanded_by', $napier);
        $this->link($battle, 'contributed_to', $later);
        $this->link($battle, 'located_at', $undated);
        // The relationship's own year, when it has one; kept inside the entity's years.
        DB::table('relationships')
            ->where('relationship_id', $this->link($battle, 'part_of', $dated))
            ->update(['temporal_start' => '1867']);
        config(['discover.for_you.per_seed' => 5]);

        $rows = collect($this->forYou([$battle])['entities'])->keyBy('name');

        // Both existed in 1868: a state with no end still stands, a person was alive.
        $this->assertSame([false, 1868], [$rows['Britain']['outgoing'], $rows['Britain']['year']]);
        $this->assertSame([true, 1868], [$rows['Robert Napier']['outgoing'], $rows['Robert Napier']['year']]);
        // They never coexisted: its own first year.
        $this->assertSame(1900, $rows['Founded later']['year']);
        // 1867 is after it ended: its last year.
        $this->assertSame(1700, $rows['With a dated link']['year']);
        // No years of its own: the seed's.
        $this->assertSame(1868, $rows['Magdala']['year']);
    }

    public function test_each_seed_gives_its_three_highest_impact_neighbours_and_eight_in_all(): void
    {
        $seeds = [];
        foreach (['A', 'B', 'C', 'D'] as $letter) {
            $seeds[$letter] = $this->entity(EntityType::PoliticalEntity, "Seed {$letter}");
            foreach ([50, 90, 70, 80, 60] as $impact) {
                $this->link($seeds[$letter], 'at_war_with', $this->entity(EntityType::PoliticalEntity, "{$letter}{$impact}", $impact));
            }
        }

        $data = $this->forYou([$seeds['B'], $seeds['A'], $seeds['C'], $seeds['D']]);

        // Three each from the first two, the last two places from the third; the fourth is not reached.
        $this->assertSame(['B90', 'B80', 'B70', 'A90', 'A80', 'A70', 'C90', 'C80'], $this->names($data['entities']));
        $this->assertSame(['Seed B', 'Seed A', 'Seed C'], $this->names($data['because']));
        $this->assertSame(
            [$seeds['B']->entity_id, $seeds['A']->entity_id, $seeds['C']->entity_id],
            array_values(array_unique(array_column($data['entities'], 'via'))),
        );
    }

    public function test_a_seed_is_never_suggested_and_a_shared_neighbour_is_given_once(): void
    {
        $rome = $this->entity(EntityType::PoliticalEntity, 'Rome', 99);
        $carthage = $this->entity(EntityType::PoliticalEntity, 'Carthage', 98);
        $shared = $this->entity(EntityType::EventWar, 'Second Punic War', 97);
        $own = $this->entity(EntityType::EventBattle, 'Battle of Zama', 50);
        $this->link($rome, 'at_war_with', $carthage);
        $this->link($rome, 'participated_in', $shared);
        $this->link($carthage, 'participated_in', $shared);
        $this->link($carthage, 'defeated_at', $own);
        $this->link($rome, 'rules', $rome);

        $data = $this->forYou([$rome, $carthage]);

        $this->assertSame(['Second Punic War', 'Battle of Zama'], $this->names($data['entities']));
        $this->assertSame([$rome->entity_id, $carthage->entity_id], array_column($data['entities'], 'via'));
    }

    public function test_hidden_neighbours_and_hidden_or_unknown_seeds_are_ignored(): void
    {
        $seed = $this->entity(EntityType::Person, 'Seed');
        $this->link($seed, 'born_in', $this->entity(EntityType::City, 'Shown city', 40));
        $this->link($seed, 'died_in', $this->entity(EntityType::City, 'Merged city', 99, ['verification_status' => VerificationStatus::Merged->value]));
        $hiddenSeed = $this->entity(EntityType::Person, 'Rejected seed', 70, ['verification_status' => VerificationStatus::Rejected->value]);
        $this->link($hiddenSeed, 'born_in', $this->entity(EntityType::City, 'City of the rejected', 90));

        $data = $this->forYou([(string) Str::uuid(), $hiddenSeed, $seed]);

        $this->assertSame(['Shown city'], $this->names($data['entities']));
        $this->assertSame(['Seed'], $this->names($data['because']));
    }

    public function test_the_surer_relationship_names_the_relation_and_breaks_a_tie(): void
    {
        $seed = $this->entity(EntityType::Person, 'Seed');
        $twice = $this->entity(EntityType::PoliticalEntity, 'Linked twice', 80);
        $this->link($seed, 'rules', $twice, 'low');
        $this->link($seed, 'founded', $twice, 'high');
        $unsure = $this->entity(EntityType::PoliticalEntity, 'Same impact, unsure', 70);
        $sure = $this->entity(EntityType::PoliticalEntity, 'Same impact, sure', 70);
        $this->link($seed, 'resided_in', $unsure, 'low');
        $this->link($seed, 'resided_in', $sure, 'high');
        $this->link($seed, 'born_in', $this->entity(EntityType::City, 'Unknown impact', 0, ['impact_score' => null]));
        $this->link($seed, 'died_in', $this->entity(EntityType::City, 'Low impact', 1));
        config(['discover.for_you.per_seed' => 5]);

        $entities = $this->forYou([$seed])['entities'];

        $this->assertSame(['Linked twice', 'Same impact, sure', 'Same impact, unsure', 'Low impact', 'Unknown impact'], $this->names($entities));
        $this->assertSame('founded', $entities[0]['relation']);
    }

    public function test_a_hub_seed_is_walked_only_so_far(): void
    {
        config(['discover.for_you.walk' => 4]);
        $hub = $this->entity(EntityType::EventWar, 'A world war');
        // Outgoing, in relationship-type order: part_of, then participated_in, then fought_at.
        $this->link($hub, 'fought_at', $this->entity(EntityType::City, 'Past the limit', 99));
        $this->link($hub, 'participated_in', $this->entity(EntityType::PoliticalEntity, 'Second out', 20));
        $this->link($hub, 'part_of', $this->entity(EntityType::EventWar, 'First out', 10));
        // Incoming: three soldiers, two of them walked.
        foreach ([30, 31, 32] as $impact) {
            $this->link($this->entity(EntityType::Person, "Soldier {$impact}", $impact), 'participated_in', $hub);
        }

        $entities = $this->forYou([$hub])['entities'];

        $this->assertCount(3, $entities);
        $this->assertNotContains('Past the limit', $this->names($entities));
        $this->assertSame(1, count(array_intersect(['First out', 'Second out'], $this->names($entities))));
        $this->assertSame(2, count(array_filter($this->names($entities), fn (string $name): bool => str_starts_with($name, 'Soldier'))));
    }

    public function test_chronicles_that_name_a_seed_come_by_impact_as_rows_of_the_chronicle_list(): void
    {
        $older = $this->entity(EntityType::Person, 'Opened earlier');
        $recent = $this->entity(EntityType::Person, 'Opened last');
        $other = $this->entity(EntityType::Person, 'Somebody else');

        $named = $this->chronicle('Names the seed', 80);
        $this->entry($named, [$older, $other]);
        $this->entry($named, [$older]);
        $byRelation = $this->chronicle('Built on its relationship', 90);
        $this->entry($byRelation, [], $this->link($other, 'mentor_of', $recent));
        $both = $this->chronicle('Names both seeds', 70);
        $this->entry($both, [$older]);
        $this->entry($both, [$recent]);
        $unrelated = $this->chronicle('About somebody else', 99);
        $this->entry($unrelated, [$other], $this->link($other, 'born_in', $this->entity(EntityType::City, 'Elsewhere')));
        $this->entry($this->chronicle('Archived', 99, ['status' => 'archived']), [$older]);
        foreach ([60, 50, 40] as $impact) {
            $this->entry($this->chronicle("Impact {$impact}", $impact), [$older]);
        }

        $data = $this->forYou([$recent, $older]);

        $this->assertSame(
            ['Built on its relationship', 'Names the seed', 'Names both seeds', 'Impact 60'],
            array_column($data['chronicles'], 'title'),
        );
        $this->assertSame(
            [$recent->entity_id, $older->entity_id, $recent->entity_id, $older->entity_id],
            array_column($data['chronicles'], 'via'),
        );

        // The same rows as GET /chronicles, plus `via`.
        $listed = collect($this->getJson('/api/v1/chronicles?per_page=50')->assertOk()->json('data'))->keyBy('slug');
        foreach ($data['chronicles'] as $row) {
            $via = $row['via'];
            unset($row['via']);
            $this->assertSame($listed[$row['slug']], $row);
            $this->assertContains($via, [$recent->entity_id, $older->entity_id]);
        }
        $this->assertSame(2, $data['chronicles'][1]['entry_count']);
    }

    public function test_chronicles_of_equal_impact_put_the_more_recent_seed_first(): void
    {
        $recent = $this->entity(EntityType::Person, 'Opened last');
        $older = $this->entity(EntityType::Person, 'Opened earlier');
        $this->entry($this->chronicle('A: for the older seed', 50), [$older]);
        $this->entry($this->chronicle('B: for the recent seed', 50), [$recent]);
        $this->entry($this->chronicle('C: undated impact', 0, ['impact_score' => null]), [$recent]);

        $this->assertSame(
            ['B: for the recent seed', 'A: for the older seed', 'C: undated impact'],
            array_column($this->forYou([$recent, $older])['chronicles'], 'title'),
        );
    }

    public function test_battle_maps_of_seeds_and_of_suggested_entities_come_as_rows_of_the_story_list(): void
    {
        $seed = $this->entity(EntityType::EventBattle, 'Battle of Hastings');
        $second = $this->entity(EntityType::Person, 'Harold Godwinson');
        $suggested = $this->entity(EntityType::EventBattle, 'Battle of Stamford Bridge', 90);
        $notSuggested = $this->entity(EntityType::EventBattle, 'Battle of Fulford', 80);
        $this->link($second, 'victorious_at', $suggested);
        $this->story($suggested, 'battle-of-stamford-bridge', 1066);
        $this->story($seed, 'battle-of-hastings', 1066);
        $this->story($seed, 'battle-of-hastings-night', 1066);
        $this->story($notSuggested, 'battle-of-fulford', 1066);
        $this->story($this->entity(EntityType::EventBattle, 'Fourth story', 70), 'fourth');

        $data = $this->forYou([$second, $seed]);

        // The seeds' own first (in the order given), then the suggested entities'.
        $this->assertSame(
            ['battle-of-hastings', 'battle-of-hastings-night', 'battle-of-stamford-bridge'],
            array_column($data['stories'], 'slug'),
        );
        $this->assertSame([$seed->entity_id, $seed->entity_id, $second->entity_id], array_column($data['stories'], 'via'));
        $this->assertSame(['Harold Godwinson', 'Battle of Hastings'], $this->names($data['because']));

        $listed = collect($this->getJson('/api/v1/map-stories?per_page=50')->assertOk()->json('data'))->keyBy('slug');
        foreach ($data['stories'] as $row) {
            unset($row['via']);
            $this->assertSame($listed[$row['slug']], $row);
        }
    }

    public function test_at_most_three_battle_maps(): void
    {
        $seed = $this->entity(EntityType::EventWar, 'A long war');
        foreach (['d', 'b', 'a', 'c'] as $slug) {
            $this->story($seed, "campaign-{$slug}");
        }

        $this->assertSame(['campaign-a', 'campaign-b', 'campaign-c'], array_column($this->forYou([$seed])['stories'], 'slug'));
    }

    public function test_seeds_that_lead_nowhere_give_an_empty_answer(): void
    {
        $loner = $this->entity(EntityType::Person, 'Loner');

        foreach ([[$loner], [(string) Str::uuid()], [$loner, $loner]] as $seeds) {
            $this->assertSame(['because' => [], 'entities' => [], 'chronicles' => [], 'stories' => []], $this->forYou($seeds));
        }
    }

    public function test_ids_are_given_as_a_list_too_and_in_any_case(): void
    {
        $seed = $this->entity(EntityType::Person, 'Seed');
        $this->link($seed, 'born_in', $this->entity(EntityType::City, 'Birthplace'));

        $data = $this->getJson('/api/v1/discover/for-you?ids[]='.strtoupper($seed->entity_id).'&ids[]='.$seed->entity_id)->assertOk()->json('data');

        $this->assertSame(['Birthplace'], $this->names($data['entities']));
        $this->assertSame([['id' => $seed->entity_id, 'name' => 'Seed']], $data['because']);
    }

    public function test_it_takes_one_to_twelve_uuids(): void
    {
        $uuids = fn (int $n): string => implode(',', array_map(fn (): string => (string) Str::uuid(), range(1, $n)));

        $this->getJson('/api/v1/discover/for-you?ids='.$uuids(12))->assertOk();
        $this->getJson('/api/v1/discover/for-you?ids='.$uuids(13))->assertStatus(422)->assertJsonValidationErrors('ids');
        $this->getJson('/api/v1/discover/for-you')->assertStatus(422)->assertJsonValidationErrors('ids');
        $this->getJson('/api/v1/discover/for-you?ids=')->assertStatus(422)->assertJsonValidationErrors('ids');
        $this->getJson('/api/v1/discover/for-you?ids=hannibal')->assertStatus(422)->assertJsonValidationErrors('ids.0');
        $this->getJson('/api/v1/discover/for-you?ids='.$uuids(1).',42')->assertStatus(422)->assertJsonValidationErrors('ids.1');
    }
}
