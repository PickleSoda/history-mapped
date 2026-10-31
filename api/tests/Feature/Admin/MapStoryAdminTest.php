<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\User;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\Feature\MapStory\MapStoryFixture;
use Tests\TestCase;

class MapStoryAdminTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    private Entity $battle;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = MapStoryFixture::directory();
        $this->battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    private function story(): MapStory
    {
        $doc = MapStoryFixture::v2Document();
        file_put_contents($this->dir.'/'.$doc['slug'].'.json', MapStoryFile::encode(MapStoryFile::fromArray($doc)));
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();

        return MapStory::query()->sole();
    }

    /** The document the editor holds, edited. */
    private function edited(MapStory $story, callable $edit): string
    {
        $doc = MapStoryFile::authored($story->fresh()->document);
        $edit($doc);

        return (string) json_encode($doc, MapStoryFile::JSON_FLAGS);
    }

    public function test_index_lists_and_filters_stories(): void
    {
        $story = $this->story();
        $admin = $this->userWithRole('admin');

        $this->actingAs($admin)->get('/map-stories')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('map-stories/index')
                ->has('stories.data', 1)
                ->where('stories.data.0.slug', 'battle-of-testfield')
                ->where('stories.data.0.edited', false)
                ->where('stories.data.0.entity.name', 'Battle of Testfield'));

        $this->actingAs($admin)->get('/map-stories?edited=1')
            ->assertInertia(fn (Assert $page) => $page->has('stories.data', 0));
        $this->actingAs($admin)->get('/map-stories?kind=epidemic')
            ->assertInertia(fn (Assert $page) => $page->has('stories.data', 0));
        $this->actingAs($admin)->get('/map-stories?search=testf')
            ->assertInertia(fn (Assert $page) => $page->has('stories.data', 1));
        $this->assertSame($story->slug, 'battle-of-testfield');
    }

    public function test_edit_page_carries_the_authored_document_and_the_vocabulary(): void
    {
        $this->story();

        $this->actingAs($this->userWithRole('admin'))->get('/map-stories/battle-of-testfield/edit')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('map-stories/edit')
                ->where('story.slug', 'battle-of-testfield')
                ->where('document_json', fn (string $json) => str_contains($json, '"slug":"battle-of-testfield"') && ! str_contains($json, 'entity_id'))
                ->where('can_edit', true)
                ->where('ai_context.type', 'entity')
                ->has('vocabulary.unit_kinds')
                ->has('vocabulary.feature_kinds.route')
                ->where('preview_url', config('app.frontend_url')));
    }

    public function test_update_saves_and_returns_warnings_or_blocks_on_errors(): void
    {
        $story = $this->story();
        $admin = $this->userWithRole('admin');

        $this->actingAs($admin)->putJson('/map-stories/battle-of-testfield', [
            'document' => $this->edited($story, fn ($d) => $d->units[0]->kind = 'dragons'),
        ])->assertStatus(422)->assertJsonPath('errors.0', fn (string $e) => str_contains($e, "'dragons'"));
        $this->assertSame(1, $story->revisions()->count());

        $this->actingAs($admin)->putJson('/map-stories/battle-of-testfield', [
            'document' => $this->edited($story, fn ($d) => $d->steps[0]->title = 'Deployment at dawn'),
            'note' => 'clearer title',
        ])->assertOk()
            ->assertJsonPath('story.edited', true)
            ->assertJsonPath('errors', [])
            ->assertJsonStructure(['story', 'document_json', 'warnings']);

        $story->refresh();
        $this->assertSame('Deployment at dawn', $story->document->steps[0]->title);
        $this->assertSame($admin->id, $story->edited_by);
        $this->assertSame(['admin', 'clearer title'], [$story->revisions()->first()->source, $story->revisions()->first()->note]);

        $this->actingAs($admin)->putJson('/map-stories/battle-of-testfield', ['document' => '[1, 2'])
            ->assertStatus(422)->assertJsonPath('errors.0', 'document: not a JSON object');
    }

    public function test_validate_is_a_dry_run(): void
    {
        $story = $this->story();

        $this->actingAs($this->userWithRole('admin'))->postJson('/map-stories/battle-of-testfield/validate', [
            'document' => $this->edited($story, function ($d): void {
                $d->steps[1]->moves = [];
                $d->steps[1]->positions->{'blue-horse'} = (object) ['at' => [16.2, 41.31]];
            }),
        ])->assertOk()
            ->assertJsonPath('errors', [])
            ->assertJsonPath('warnings', fn (array $w) => collect($w)->contains(fn ($m) => str_contains($m, 'blue-horse moves')));

        $this->assertFalse($story->fresh()->isEdited());
    }

    public function test_revisions_list_show_and_restore(): void
    {
        $story = $this->story();
        $admin = $this->userWithRole('admin');
        $this->actingAs($admin)->putJson('/map-stories/battle-of-testfield', [
            'document' => $this->edited($story, fn ($d) => $d->title = 'Renamed'),
        ])->assertOk();

        $list = $this->actingAs($admin)->getJson('/map-stories/battle-of-testfield/revisions')
            ->assertOk()->assertJsonCount(2, 'data')->json('data');
        $this->assertSame(['admin', 'import'], array_column($list, 'source'));
        $this->assertSame($admin->name, $list[0]['user']);

        $first = $list[1]['id'];
        $this->actingAs($admin)->getJson("/map-stories/battle-of-testfield/revisions/{$first}")
            ->assertOk()->assertJsonPath('data.document_json', fn (string $json) => str_contains($json, '"title":"Battle of Testfield"'));

        $this->actingAs($admin)->postJson("/map-stories/battle-of-testfield/revisions/{$first}/restore")
            ->assertOk()->assertJsonPath('story.title', 'Battle of Testfield')->assertJsonPath('story.edited', false);
        $this->assertSame('restore', $story->revisions()->first()->source);
    }

    public function test_store_creates_a_skeleton_for_an_entity_or_a_chronicle(): void
    {
        $admin = $this->userWithRole('admin');
        $this->battle->primaryLocation()->create(['is_primary' => true, 'geom' => ['type' => 'Point', 'coordinates' => [16.13, 41.3]]]);

        $this->actingAs($admin)->post('/map-stories', [
            'entity_id' => $this->battle->entity_id, 'kind' => 'battle', 'title' => 'Battle of Testfield', 'year' => -216,
        ])->assertRedirect('/map-stories/battle-of-testfield/edit');

        $story = MapStory::query()->sole();
        $this->assertSame($this->battle->entity_id, $story->entity_id);
        $this->assertSame(['side-a-main', 'side-b-main'], array_keys((array) $story->document->steps[0]->positions));
        $this->assertSame(16.13, $story->document->steps[0]->positions->{'side-a-main'}->at[0]);
        $this->assertSame('admin', $story->revisions()->sole()->source);

        $chronicle = Chronicle::factory()->create(['slug' => 'testland-trade', 'title' => 'Testland trade']);
        $this->actingAs($admin)->post('/map-stories', [
            'chronicle_id' => $chronicle->chronicle_id, 'kind' => 'trade_route', 'title' => 'Testland trade map', 'year' => 900,
        ])->assertRedirect('/map-stories/testland-trade-map/edit');
        $layer = MapStory::query()->where('slug', 'testland-trade-map')->sole();
        $this->assertSame($chronicle->chronicle_id, $layer->chronicle_id);
        $this->assertNull($layer->entity_id);
    }

    public function test_destroy_hard_deletes_the_row(): void
    {
        $this->story();

        $this->actingAs($this->userWithRole('admin'))->delete('/map-stories/battle-of-testfield')
            ->assertRedirect('/map-stories')
            ->assertSessionHas('success', fn (string $m) => str_contains($m, 'next map-stories:sync'));
        $this->assertSame(0, MapStory::query()->count());
        $this->assertDatabaseCount('map_story_revisions', 0);
    }

    public function test_writes_need_entities_write(): void
    {
        $story = $this->story();
        $viewer = $this->userWithPermissions(['admin.access']);

        $this->actingAs($viewer)->get('/map-stories/battle-of-testfield/edit')
            ->assertOk()->assertInertia(fn (Assert $page) => $page->where('can_edit', false));
        $this->actingAs($viewer)->putJson('/map-stories/battle-of-testfield', ['document' => $this->edited($story, fn ($d) => $d->title = 'X')])
            ->assertForbidden();
        $this->actingAs($viewer)->delete('/map-stories/battle-of-testfield')->assertForbidden();
        $this->actingAs(User::factory()->create())->get('/map-stories')->assertForbidden();
    }

    public function test_entity_edit_page_lists_its_map_stories(): void
    {
        $this->story();

        $this->actingAs($this->userWithRole('admin'))->get("/entities/{$this->battle->entity_id}/edit")
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('map_stories.0.slug', 'battle-of-testfield')->has('map_story_kinds'));
    }
}
