<?php

declare(strict_types=1);

namespace Tests\Feature\Collection;

use App\Enums\EntityType;
use App\Enums\TagFacet;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Collection;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\Tag;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Tests\TestCase;

/** GET /api/v1/collections and /collections/{slug}. */
class CollectionApiTest extends TestCase
{
    use RefreshDatabase;

    /** @param  array<string, mixed>  $attributes */
    private function collection(string $slug, array $attributes = []): Collection
    {
        return Collection::query()->create([
            'slug' => $slug,
            'title' => ucwords(str_replace('-', ' ', $slug)),
            'items' => [],
            ...$attributes,
        ]);
    }

    public function test_index_lists_published_collections_in_order_with_cover_and_counts(): void
    {
        $rome = Entity::factory()->create(['name' => 'Roman Empire', 'wikidata_id' => 'Q2277']);
        Chronicle::factory()->create(['slug' => 'punic-wars']);
        $this->collection('zeta', ['sort_order' => 1]);
        $this->collection('the-roman-world', [
            'title' => 'The Roman World',
            'subtitle' => 'Republic and empire',
            'description' => 'Two sentences. Of markdown.',
            'cover_entity_id' => $rome->entity_id,
            'sort_order' => 1,
            'items' => [
                ['kind' => 'entity', 'ref' => 'Q2277'],
                ['kind' => 'entity', 'ref' => 'Q404404404'],
                ['kind' => 'chronicle', 'ref' => 'punic-wars'],
                ['kind' => 'story', 'ref' => 'missing-story'],
            ],
        ]);
        $this->collection('first', ['sort_order' => 0]);
        $this->collection('hidden', ['status' => 'draft']);

        $response = $this->getJson('/api/v1/collections')
            ->assertOk()
            ->assertHeader('Cache-Control', 'max-age=300, public')
            ->assertJsonPath('data.*.slug', ['first', 'the-roman-world', 'zeta']);

        $response->assertJsonPath('data.1.title', 'The Roman World')
            ->assertJsonPath('data.1.subtitle', 'Republic and empire')
            ->assertJsonPath('data.1.description', 'Two sentences. Of markdown.')
            ->assertJsonPath('data.1.cover.id', $rome->entity_id)
            ->assertJsonPath('data.1.cover.name', 'Roman Empire')
            ->assertJsonPath('data.1.item_count', 2)
            ->assertJsonPath('data.1.items_by_kind', ['entity' => 1, 'chronicle' => 1, 'story' => 0, 'tag' => 0])
            ->assertJsonPath('data.0.cover', null)
            ->assertJsonPath('data.0.item_count', 0)
            ->assertJsonMissingPath('data.1.items');
    }

    public function test_show_resolves_every_kind_in_order_and_drops_missing_refs(): void
    {
        $rome = Entity::factory()->create(['name' => 'Roman Empire', 'wikidata_id' => 'Q2277', 'impact_score' => 90]);
        Entity::factory()->create(['name' => 'Roman Empire (duplicate)', 'wikidata_id' => 'Q2277', 'impact_score' => 10]);
        $caesar = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Julius Caesar', 'wikidata_id' => null]);
        $cannaeBattle = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Cannae']);
        $chronicle = Chronicle::factory()->create(['slug' => 'punic-wars', 'title' => 'The Punic Wars']);
        ChronicleEntry::factory()->count(2)->create(['chronicle_id' => $chronicle->chronicle_id]);
        $story = MapStory::query()->create([
            'entity_id' => $cannaeBattle->entity_id,
            'slug' => 'battle-of-cannae',
            'kind' => 'battle',
            'title' => 'Battle of Cannae',
            'year' => -216,
            'step_count' => 6,
            'document' => (object) [],
        ]);
        Tag::query()->create(['slug' => 'classical', 'name' => 'Classical antiquity', 'facet' => TagFacet::Era, 'start_year' => -800, 'end_year' => 500]);
        DB::table('chronicle_tags')->insert(['chronicle_id' => $chronicle->chronicle_id, 'tag' => 'classical']);

        $this->collection('the-roman-world', [
            'cover_entity_id' => $rome->entity_id,
            'items' => [
                ['kind' => 'entity', 'ref' => 'Q2277', 'note' => 'The empire.'],
                ['kind' => 'story', 'ref' => 'battle-of-cannae'],
                ['kind' => 'entity', 'ref' => 'Q999999'],
                ['kind' => 'chronicle', 'ref' => 'punic-wars'],
                ['kind' => 'tag', 'ref' => 'classical'],
                ['kind' => 'entity', 'ref' => strtoupper($caesar->entity_id), 'note' => 'By uuid.'],
                ['kind' => 'chronicle', 'ref' => 'gone'],
                ['kind' => 'entity', 'ref' => 'not a ref'],
            ],
        ]);

        Log::spy();

        $response = $this->getJson('/api/v1/collections/the-roman-world')
            ->assertOk()
            ->assertHeader('Cache-Control', 'max-age=300, public')
            ->assertJsonPath('data.slug', 'the-roman-world')
            ->assertJsonPath('data.cover.id', $rome->entity_id)
            ->assertJsonPath('data.item_count', 5)
            ->assertJsonPath('data.items_by_kind', ['entity' => 2, 'chronicle' => 1, 'story' => 1, 'tag' => 1])
            ->assertJsonPath('data.items.*.kind', ['entity', 'story', 'chronicle', 'tag', 'entity']);

        $response->assertJsonPath('data.items.0.note', 'The empire.')
            ->assertJsonPath('data.items.0.entity.id', $rome->entity_id)
            ->assertJsonPath('data.items.0.entity.name', 'Roman Empire')
            ->assertJsonPath('data.items.1.note', null)
            ->assertJsonPath('data.items.1.story', [
                'id' => $story->story_id,
                'slug' => 'battle-of-cannae',
                'kind' => 'battle',
                'title' => 'Battle of Cannae',
                'year' => -216,
                'step_count' => 6,
                'entity' => ['id' => $cannaeBattle->entity_id, 'name' => 'Battle of Cannae', 'entity_type' => 'event_battle'],
                'chronicle' => null,
            ])
            ->assertJsonPath('data.items.2.chronicle.slug', 'punic-wars')
            ->assertJsonPath('data.items.2.chronicle.title', 'The Punic Wars')
            ->assertJsonPath('data.items.2.chronicle.entry_count', 2)
            ->assertJsonPath('data.items.2.chronicle.tags', ['classical'])
            ->assertJsonPath('data.items.2.chronicle.map_story', null)
            ->assertJsonMissingPath('data.items.2.chronicle.entries')
            ->assertJsonPath('data.items.3.tag', [
                'slug' => 'classical',
                'name' => 'Classical antiquity',
                'facet' => 'era',
                'parent' => null,
                'description' => null,
                'start_year' => -800,
                'end_year' => 500,
                'chronicle_count' => 1,
                'entity_count' => 0,
            ])
            ->assertJsonPath('data.items.4.entity.id', $caesar->entity_id)
            ->assertJsonPath('data.items.4.note', 'By uuid.')
            ->assertJsonMissingPath('data.items.0.story');

        Log::shouldHaveReceived('warning')->times(3);
    }

    public function test_show_is_404_for_an_unknown_or_draft_collection(): void
    {
        $this->collection('hidden', ['status' => 'draft']);

        $this->getJson('/api/v1/collections/hidden')->assertNotFound();
        $this->getJson('/api/v1/collections/nope')->assertNotFound();
    }

    public function test_a_deleted_cover_entity_leaves_no_cover(): void
    {
        $rome = Entity::factory()->create();
        $this->collection('the-roman-world', ['cover_entity_id' => $rome->entity_id]);

        $rome->delete();

        $this->getJson('/api/v1/collections/the-roman-world')
            ->assertOk()
            ->assertJsonPath('data.cover', null);
    }
}
