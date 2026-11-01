<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/** GET /api/v1/map-stories: the battle-maps list. */
class MapStoryIndexApiTest extends TestCase
{
    use RefreshDatabase;

    /**
     * A story belongs to an entity or a chronicle (or both): a fresh entity unless one is given.
     *
     * @param  array<string, mixed>  $attributes
     */
    private function story(string $slug, string $kind, string $title, ?int $year, array $attributes = []): MapStory
    {
        if (! array_key_exists('entity_id', $attributes) && ! array_key_exists('chronicle_id', $attributes)) {
            $attributes['entity_id'] = Entity::factory()->create()->entity_id;
        }

        return MapStory::query()->create([
            'slug' => $slug,
            'kind' => $kind,
            'title' => $title,
            'year' => $year,
            'step_count' => 3,
            'document' => (object) ['slug' => $slug],
            ...$attributes,
        ]);
    }

    public function test_index_lists_summaries_with_their_entity_and_chronicle(): void
    {
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Cannae']);
        $chronicle = Chronicle::factory()->create(['slug' => 'black-death', 'title' => 'The Black Death']);
        $cannae = $this->story('battle-of-cannae', 'battle', 'Battle of Cannae', -216, ['entity_id' => $battle->entity_id]);
        $plague = $this->story('black-death-spread', 'epidemic', 'The Black Death spreads', 1347, ['chronicle_id' => $chronicle->chronicle_id]);

        $response = $this->getJson('/api/v1/map-stories')->assertOk();

        $response->assertJsonPath('data', [
            [
                'id' => $cannae->story_id,
                'slug' => 'battle-of-cannae',
                'kind' => 'battle',
                'title' => 'Battle of Cannae',
                'year' => -216,
                'step_count' => 3,
                'entity' => ['id' => $battle->entity_id, 'name' => 'Battle of Cannae', 'entity_type' => 'event_battle'],
                'chronicle' => null,
            ],
            [
                'id' => $plague->story_id,
                'slug' => 'black-death-spread',
                'kind' => 'epidemic',
                'title' => 'The Black Death spreads',
                'year' => 1347,
                'step_count' => 3,
                'entity' => null,
                'chronicle' => ['slug' => 'black-death', 'title' => 'The Black Death'],
            ],
        ])
            ->assertJsonPath('meta.total', 2)
            ->assertJsonPath('meta.current_page', 1)
            ->assertJsonMissingPath('data.0.document');
    }

    public function test_index_filters_by_one_or_several_kinds(): void
    {
        $this->story('battle-a', 'battle', 'A', 100);
        $this->story('siege-b', 'siege', 'B', 200);
        $this->story('trade-c', 'trade_route', 'C', 300);

        $this->getJson('/api/v1/map-stories?kind=siege')
            ->assertOk()
            ->assertJsonPath('data.*.slug', ['siege-b']);

        $this->getJson('/api/v1/map-stories?kind=battle,siege')
            ->assertOk()
            ->assertJsonPath('data.*.slug', ['battle-a', 'siege-b']);

        $this->getJson('/api/v1/map-stories?kind[]=trade_route')
            ->assertOk()
            ->assertJsonPath('data.*.slug', ['trade-c']);

        $this->getJson('/api/v1/map-stories?kind=dance')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('kind.0');
    }

    public function test_index_sorts_by_year_by_default_and_by_title_on_request(): void
    {
        $this->story('undated', 'battle', 'Alpha', null);
        $this->story('late', 'battle', 'Bravo', 1805);
        $this->story('early', 'battle', 'Charlie', -490);

        $this->getJson('/api/v1/map-stories')
            ->assertJsonPath('data.*.slug', ['early', 'late', 'undated']);

        $this->getJson('/api/v1/map-stories?sort=year')
            ->assertJsonPath('data.*.slug', ['early', 'late', 'undated']);

        $this->getJson('/api/v1/map-stories?sort=title')
            ->assertJsonPath('data.*.slug', ['undated', 'late', 'early']);

        $this->getJson('/api/v1/map-stories?sort=impact')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('sort');
    }

    public function test_index_paginates_and_caps_per_page(): void
    {
        foreach (range(1, 5) as $i) {
            $this->story("battle-{$i}", 'battle', "Battle {$i}", 1000 + $i);
        }

        $this->getJson('/api/v1/map-stories?per_page=2&page=2')
            ->assertOk()
            ->assertJsonPath('data.*.slug', ['battle-3', 'battle-4'])
            ->assertJsonPath('meta.per_page', 2)
            ->assertJsonPath('meta.current_page', 2)
            ->assertJsonPath('meta.last_page', 3)
            ->assertJsonPath('meta.total', 5);

        $this->getJson('/api/v1/map-stories?per_page=101')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('per_page');

        $this->getJson('/api/v1/map-stories?page=0')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('page');
    }

    public function test_the_index_route_leaves_ambient_and_show_alone(): void
    {
        $this->story('battle-of-testfield', 'battle', 'Battle of Testfield', 1000);

        $this->getJson('/api/v1/map-stories/battle-of-testfield')
            ->assertOk()
            ->assertJsonPath('data.slug', 'battle-of-testfield');

        $this->getJson('/api/v1/map-stories/ambient?year=1000')->assertOk();
    }
}
