<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class SyncMapStoriesCommandTest extends TestCase
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

    private function battle(array $attributes = []): Entity
    {
        return Entity::factory()->ofType(EntityType::EventBattle)->create([
            'name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591', ...$attributes,
        ]);
    }

    private function sync(string ...$options): int
    {
        return $this->artisan('map-stories:sync', ['--path' => $this->dir, ...array_fill_keys($options, true)])->run();
    }

    public function test_syncs_a_story_and_resolves_its_qids_to_entities(): void
    {
        $battle = $this->battle();
        $hannibal = Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Hannibal', 'wikidata_id' => 'Q8456']);
        $carthage = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Carthage', 'wikidata_id' => 'Q6343']);
        MapStoryFixture::write($this->dir, MapStoryFixture::document());

        $this->assertSame(0, $this->sync());

        $story = MapStory::query()->sole();
        $this->assertSame('battle-of-testfield', $story->slug);
        $this->assertSame($battle->entity_id, $story->entity_id);
        $this->assertSame(['battle', 'Battle of Testfield', -216, 2], [$story->kind, $story->title, $story->year, $story->step_count]);
        $this->assertSame('resources/map-stories/battle-of-testfield.json', $story->source_path);

        $doc = $story->document;
        $this->assertSame($battle->entity_id, $doc->entity->entity_id);
        $this->assertSame($carthage->entity_id, $doc->sides[0]->polity->entity_id);
        $this->assertSame($hannibal->entity_id, $doc->sides[0]->commanders[0]->entity_id);
        $this->assertNull($doc->sides[0]->commanders[1]->entity_id, 'a Q-id the atlas lacks resolves to null');
        $this->assertSame($hannibal->entity_id, $doc->units[2]->entity_id);
        $this->assertNull($doc->units[0]->entity_id);

        // An empty JSON object stays an object through jsonb.
        $raw = DB::table('map_stories')->value('document');
        $this->assertSame('{}', json_encode(json_decode($raw)->steps[1]->positions));
    }

    public function test_skips_unchanged_files_and_resyncs_changed_or_forced_ones(): void
    {
        $this->battle();
        $doc = MapStoryFixture::document();
        MapStoryFixture::write($this->dir, $doc);
        $this->sync();

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('unchanged')
            ->assertSuccessful();

        $doc['title'] = 'Battle of Testfield (revised)';
        MapStoryFixture::write($this->dir, $doc);
        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('updated')
            ->assertSuccessful();
        $this->assertSame('Battle of Testfield (revised)', MapStory::query()->sole()->title);

        $this->artisan('map-stories:sync', ['--path' => $this->dir, '--force' => true])
            ->expectsOutputToContain('updated')
            ->assertSuccessful();
    }

    public function test_falls_back_to_the_exact_name_of_an_event_entity(): void
    {
        $battle = $this->battle(['wikidata_id' => null]);
        Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Battle of Testfield']);
        MapStoryFixture::write($this->dir, MapStoryFixture::document(wikidata: null));

        $this->assertSame(0, $this->sync());
        $this->assertSame($battle->entity_id, MapStory::query()->sole()->entity_id);
    }

    public function test_fails_a_file_whose_entity_is_not_in_the_atlas(): void
    {
        MapStoryFixture::write($this->dir, MapStoryFixture::document());

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('is not in the atlas')
            ->assertFailed();
        $this->assertSame(0, MapStory::query()->count());
    }

    public function test_fails_an_invalid_document_or_a_slug_that_is_not_its_file_name(): void
    {
        $this->battle();
        $bad = MapStoryFixture::document('battle-of-badfield');
        $bad['units'][0]['kind'] = 'dragons';
        MapStoryFixture::write($this->dir, $bad);
        MapStoryFixture::write($this->dir, MapStoryFixture::document(), 'other-name.json');

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain("'dragons'")
            ->expectsOutputToContain("must match the file name 'other-name'")
            ->assertFailed();
        $this->assertSame(0, MapStory::query()->count());
    }

    public function test_syncs_a_schema_2_story(): void
    {
        $this->battle();
        $gauls = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Gauls', 'wikidata_id' => 'Q29890']);
        $doc = MapStoryFixture::v2Document();
        $doc['sides'][0]['contingents'][0]['wikidata'] = 'Q29890';
        $doc['sides'][0]['contingents'][1]['wikidata'] = 'Q999999998';
        MapStoryFixture::write($this->dir, $doc);

        $this->assertSame(0, $this->sync());

        $story = MapStory::query()->sole();
        $doc = $story->document;
        $this->assertSame(2, $doc->schema);
        $this->assertSame('The wing rejoins the line', $doc->steps[1]->beats[0]->label);
        $this->assertNull($doc->steps[1]->terrain_state->town->held_by);
        $this->assertSame('gauls', $doc->units[0]->contingent);
        // A contingent's Q-id links like a side's polity; the authored copy drops the id.
        $this->assertSame([$gauls->entity_id, null], [$doc->sides[0]->contingents[0]->entity_id, $doc->sides[0]->contingents[1]->entity_id]);
        $this->assertObjectNotHasProperty('entity_id', MapStoryFile::authored($doc)->sides[0]->contingents[0]);
    }

    public function test_rejects_a_schema_1_story_that_uses_schema_2_fields(): void
    {
        $this->battle();
        $doc = MapStoryFixture::v2Document();
        $doc['schema'] = 1;
        MapStoryFixture::write($this->dir, $doc);

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('need schema 2 — set `schema: 2`')
            ->assertFailed();
        $this->assertSame(0, MapStory::query()->count());
    }

    public function test_prune_deletes_synced_stories_whose_file_is_gone(): void
    {
        $this->battle();
        $path = MapStoryFixture::write($this->dir, MapStoryFixture::document());
        $this->sync();
        unlink($path);

        $this->sync();
        $this->assertSame(1, MapStory::query()->count(), 'no prune without --prune');

        $this->sync('--prune');
        $this->assertSame(0, MapStory::query()->count());
    }
}
