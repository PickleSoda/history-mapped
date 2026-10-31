<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapStoryApiTest extends TestCase
{
    use RefreshDatabase;

    private function story(Entity $entity, string $slug = 'battle-of-testfield'): MapStory
    {
        return MapStory::query()->create([
            'entity_id' => $entity->entity_id,
            'slug' => $slug,
            'kind' => 'battle',
            'title' => 'Battle of Testfield',
            'year' => -216,
            'step_count' => 2,
            'document' => json_decode(json_encode(MapStoryFixture::document($slug))),
        ]);
    }

    public function test_show_returns_the_story_with_its_document(): void
    {
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create();
        $story = $this->story($battle);

        $this->getJson('/api/v1/map-stories/battle-of-testfield')
            ->assertOk()
            ->assertJsonPath('data.id', $story->story_id)
            ->assertJsonPath('data.slug', 'battle-of-testfield')
            ->assertJsonPath('data.kind', 'battle')
            ->assertJsonPath('data.year', -216)
            ->assertJsonPath('data.step_count', 2)
            ->assertJsonPath('data.entity_id', $battle->entity_id)
            ->assertJsonPath('data.document.units.0.id', 'red-foot')
            ->assertJsonPath('data.document.steps.1.moves.0.type', 'charge');

        $raw = $this->get('/api/v1/map-stories/battle-of-testfield')->getContent();
        $this->assertStringContainsString('"positions":{}', (string) $raw, 'empty objects stay objects');
    }

    public function test_show_is_404_for_an_unknown_slug(): void
    {
        $this->getJson('/api/v1/map-stories/nope')->assertNotFound();
    }

    public function test_entity_detail_carries_its_description_and_story_summaries(): void
    {
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['description' => "One.\n\nTwo."]);
        $story = $this->story($battle);
        $plain = Entity::factory()->create();

        $this->getJson("/api/v1/entities/{$battle->entity_id}")
            ->assertOk()
            ->assertJsonPath('data.description', "One.\n\nTwo.")
            ->assertJsonPath('data.map_stories', [[
                'id' => $story->story_id,
                'slug' => 'battle-of-testfield',
                'kind' => 'battle',
                'title' => 'Battle of Testfield',
                'year' => -216,
                'step_count' => 2,
            ]]);

        $this->getJson("/api/v1/entities/{$plain->entity_id}")
            ->assertOk()
            ->assertJsonPath('data.description', null)
            ->assertJsonPath('data.map_stories', []);
    }

    public function test_map_features_flag_entities_that_have_a_story(): void
    {
        $battle = Entity::factory()->verified()->ofType(EntityType::EventBattle)->create(['impact_score' => 90]);
        $other = Entity::factory()->verified()->ofType(EntityType::EventBattle)->create(['impact_score' => 90]);
        foreach ([$battle, $other] as $entity) {
            DB::statement(
                "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, geom, provenance_mode, created_by, created_at, updated_at)
                 VALUES (gen_random_uuid(), ?, 'point', 1000, 1000, ST_SetSRID(ST_MakePoint(10.5, 40.5), 4326), 'manual', 'test', NOW(), NOW())",
                [$entity->entity_id],
            );
        }
        $query = ['bbox_min_lng' => 0, 'bbox_min_lat' => 30, 'bbox_max_lng' => 30, 'bbox_max_lat' => 50, 'year' => 1000];

        $before = $this->get(route('api.v1.entities.map', $query));
        $this->story($battle);

        $flags = collect($this->getJson(route('api.v1.entities.map', $query))->json('features'))
            ->mapWithKeys(fn (array $f) => [$f['properties']['id'] => $f['properties']['has_map_story']]);
        $this->assertTrue($flags[$battle->entity_id]);
        $this->assertFalse($flags[$other->entity_id]);

        // A new story changes the ETag, so a cached map refetches.
        $after = $this->get(route('api.v1.entities.map', $query));
        $this->assertNotSame($before->headers->get('ETag'), $after->headers->get('ETag'));

        $byYear = collect($this->getJson(route('api.v1.entities.map.year', $query))->json('features'))
            ->mapWithKeys(fn (array $f) => [$f['properties']['id'] => $f['properties']['has_map_story']]);
        $this->assertTrue($byYear[$battle->entity_id]);
    }

    public function test_chronicle_resources_carry_the_description(): void
    {
        Chronicle::factory()->create(['slug' => 'punic-wars', 'title' => 'Punic Wars', 'description' => 'An introduction.', 'status' => 'published']);

        $this->getJson('/api/v1/chronicles/punic-wars')
            ->assertOk()
            ->assertJsonPath('data.description', 'An introduction.');
    }
}
