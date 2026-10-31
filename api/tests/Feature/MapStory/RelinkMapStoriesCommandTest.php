<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Actions\Entity\MergeEntitiesAction;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\MapStoryRevision;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/** `map-stories:relink`: re-resolve stored stories in place, without reading files. */
class RelinkMapStoriesCommandTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = MapStoryFixture::directory();
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    /** Sync the schema-1 fixture with only its battle in the atlas. */
    private function synced(): MapStory
    {
        Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
        MapStoryFixture::write($this->dir, MapStoryFixture::document());
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();

        return MapStory::query()->sole();
    }

    public function test_links_an_entity_created_after_the_sync_and_keeps_the_bookkeeping(): void
    {
        $story = $this->synced();
        $this->assertNull($story->document->sides[0]->commanders[0]->entity_id);
        $story->forceFill(['edited_at' => now()->addMinute(), 'edited_by' => null])->save();
        $before = $story->only(['file_hash', 'synced_at', 'edited_at', 'source_path']);
        $revisions = $story->revisions()->count();

        // The file changed meanwhile: relink must not read it.
        File::put($this->dir.'/battle-of-testfield.json', '{}');
        $hannibal = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Hannibal', 'wikidata_id' => 'Q8456']);

        $this->artisan('map-stories:relink')->expectsOutputToContain('relinked')->assertSuccessful();

        $story->refresh();
        $this->assertSame($hannibal->entity_id, $story->document->sides[0]->commanders[0]->entity_id);
        $this->assertSame($hannibal->entity_id, $story->document->units[2]->entity_id);
        $this->assertSame('Battle of Testfield', $story->title);
        $this->assertEquals($before, $story->only(['file_hash', 'synced_at', 'edited_at', 'source_path']));
        $this->assertTrue($story->isEdited(), 'an edited story stays edited');

        $this->assertSame($revisions + 1, $story->revisions()->count());
        $revision = $story->revisions()->first();
        $this->assertSame(['sync', 'relink', null], [$revision->source, $revision->note, $revision->user_id]);
        $this->assertObjectNotHasProperty('entity_id', $revision->document->sides[0]->commanders[0], 'a revision keeps the authored document');
    }

    public function test_an_unchanged_story_writes_no_revision(): void
    {
        $story = $this->synced();
        $revisions = MapStoryRevision::query()->count();
        $updated = $story->updated_at;

        $this->artisan('map-stories:relink', ['--slug' => ['battle-of-testfield']])
            ->expectsOutputToContain('unchanged')
            ->assertSuccessful();

        $this->assertSame($revisions, MapStoryRevision::query()->count());
        $this->assertEquals($updated, $story->refresh()->updated_at);
    }

    public function test_an_ambient_story_with_shown_entities_is_unchanged_on_a_second_run(): void
    {
        Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['name' => 'Plague of Testland', 'wikidata_id' => 'Q42005']);
        $horde = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Golden Horde', 'wikidata_id' => 'Q79965']);
        DB::statement(
            "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, territory_geom, provenance_mode, created_by, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'territory', 1240, 1400, ST_SetSRID(ST_GeomFromText('POLYGON((40 45, 50 45, 50 55, 40 55, 40 45))'), 4326), 'manual', 'test', NOW(), NOW())",
            [$horde->entity_id],
        );
        $doc = MapStoryFixture::v3Document();
        $doc['steps'][0]['entities'][] = ['name' => 'Golden Horde', 'wikidata' => 'Q79965', 'show' => true];
        MapStoryFixture::write($this->dir, $doc);
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();
        $revisions = MapStoryRevision::query()->count();

        $this->artisan('map-stories:relink')->expectsOutputToContain('unchanged')->assertSuccessful();
        $this->assertSame($revisions, MapStoryRevision::query()->count());
    }

    public function test_a_stale_entity_id_is_recomputed_after_a_merge(): void
    {
        Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
        $loser = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Hannibal', 'wikidata_id' => 'Q8456', 'impact_score' => 90]);
        $survivor = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Hannibal Barca', 'wikidata_id' => 'Q8456', 'impact_score' => 10]);
        $carthage = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Carthage', 'wikidata_id' => 'Q6343']);
        MapStoryFixture::write($this->dir, MapStoryFixture::document());
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();
        $this->assertSame($loser->entity_id, MapStory::query()->sole()->document->sides[0]->commanders[0]->entity_id);

        (new MergeEntitiesAction)($survivor->entity_id, $loser->entity_id);
        $carthage->delete();

        $this->artisan('map-stories:relink')->expectsOutputToContain('relinked')->assertSuccessful();

        $doc = MapStory::query()->sole()->document;
        $this->assertSame($survivor->entity_id, $doc->sides[0]->commanders[0]->entity_id, 'the Q-id re-resolves to the survivor');
        $this->assertNull($doc->sides[0]->polity->entity_id, 'a deleted entity resolves to null');
    }

    public function test_reports_a_story_that_no_longer_resolves(): void
    {
        $story = $this->synced();
        // (Deleting the story's entity would delete the story.)
        Entity::query()->whereKey($story->entity_id)->update(['wikidata_id' => 'Q1', 'name' => 'Something else']);
        $revisions = MapStoryRevision::query()->count();

        $this->artisan('map-stories:relink')
            ->expectsOutputToContain("failed: entity 'Battle of Testfield' (Q179591) is not in the atlas")
            ->assertFailed();
        $this->assertSame($revisions, MapStoryRevision::query()->count());
    }
}
