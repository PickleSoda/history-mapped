<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\EntityType;
use App\Enums\TagFacet;
use App\Enums\TagSource;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\Tag;
use Database\Seeders\TagSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class TagApiTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(TagSeeder::class);
    }

    private function chronicle(string $title, array $tags): Chronicle
    {
        $chronicle = Chronicle::factory()->create(['title' => $title, 'start_year' => null, 'end_year' => null]);
        app(SyncTagsAction::class)($chronicle, $tags, TagSource::Curated);

        return $chronicle;
    }

    public function test_tags_index_lists_vocabulary_with_counts_and_hides_unused_topics(): void
    {
        $this->chronicle('Tang China', ['china', 'medieval', 'polity']);
        app(SyncTagsAction::class)(Entity::factory()->create(), ['Silk'], TagSource::Manual);
        Tag::query()->create(['slug' => 'orphan-topic', 'name' => 'Orphan Topic', 'facet' => TagFacet::Topic]);

        $res = $this->getJson('/api/v1/tags')->assertOk();

        $tags = collect($res->json('data'))->keyBy('slug');
        $this->assertSame('east-asia', $tags['china']['parent']);
        $this->assertSame(1, $tags['china']['chronicle_count']);
        $this->assertSame(1, $tags['asia']['chronicle_count']);
        $this->assertSame(1, $tags['silk']['entity_count']);
        $this->assertFalse($tags->has('orphan-topic'));
        $this->assertSame(['era', 'region', 'theme', 'type', 'topic'], array_column($res->json('facets'), 'key'));
        // Facet order first, vocabulary order within a facet.
        $this->assertSame('prehistory', $res->json('data.0.slug'));
    }

    public function test_chronicle_tag_filter_is_and_across_facets_or_within_a_facet(): void
    {
        $this->chronicle('Song China', ['china', 'medieval', 'regional']);
        $this->chronicle('Carolingians', ['western-europe', 'medieval', 'regional']);
        $this->chronicle('Han China', ['china', 'classical', 'polity']);

        $titles = fn (array $query): array => collect(
            $this->getJson('/api/v1/chronicles?'.http_build_query($query + ['sort' => 'title']))->assertOk()->json('data'),
        )->pluck('title')->all();

        $this->assertSame(['Carolingians', 'Song China'], $titles(['tags' => ['medieval']]));
        $this->assertSame(['Song China'], $titles(['tags' => ['medieval', 'asia']]));
        $this->assertSame(['Carolingians', 'Song China'], $titles(['tags' => ['medieval', 'asia', 'europe']]));
        $this->assertSame(['Han China', 'Song China'], $titles(['tags' => 'east-asia']));
        $this->assertSame([], $titles(['tags' => ['medieval', 'no-such-tag']]));
    }

    public function test_chronicle_search_matches_tag_names_and_payload_carries_tag_slugs(): void
    {
        $this->chronicle('Mycenae', ['bronze-age', 'greece']);
        $this->chronicle('Song China', ['china', 'medieval']);

        $res = $this->getJson('/api/v1/chronicles?search=bronze')->assertOk();

        $this->assertSame(['Mycenae'], array_column($res->json('data'), 'title'));
        $this->assertEqualsCanonicalizing(
            ['ancient', 'bronze-age', 'europe', 'greece'],
            $res->json('data.0.tags'),
        );

        $slug = Chronicle::where('title', 'Mycenae')->value('slug');
        $this->assertContains('greece', $this->getJson("/api/v1/chronicles/{$slug}")->assertOk()->json('data.tags'));
    }

    public function test_entity_list_filters_by_one_or_many_tags(): void
    {
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Didgori']);
        $treaty = Entity::factory()->ofType(EntityType::EventTreaty)->create(['name' => 'Some Treaty']);
        app(SyncTagsAction::class)($battle, ['war', 'caucasus'], TagSource::Manual);
        app(SyncTagsAction::class)($treaty, ['diplomacy-law', 'caucasus'], TagSource::Manual);

        $names = fn (string $query): array => collect($this->getJson("/api/v1/entities?{$query}")->assertOk()->json('data'))
            ->pluck('name')->sort()->values()->all();

        // The single-tag filter used to throw a TypeError.
        $this->assertSame(['Didgori'], $names('tag=war'));
        $this->assertSame(['Didgori', 'Some Treaty'], $names('tags[]=asia'));
        $this->assertSame(['Didgori'], $names('tags=war,caucasus'));
        $this->assertSame(['Didgori', 'Some Treaty'], $names('tags=war,diplomacy-law'));
    }
}
