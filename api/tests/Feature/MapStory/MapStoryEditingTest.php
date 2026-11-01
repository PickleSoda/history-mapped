<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Actions\MapStory\PatchMapStoryAction;
use App\Actions\MapStory\RestoreMapStoryRevisionAction;
use App\Actions\MapStory\SaveMapStoryAction;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\MapStoryRevision;
use App\Models\User;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use stdClass;
use Tests\TestCase;

/**
 * The DB row is the live copy: saves write revisions, sync keeps admin edits
 * unless forced, export writes the builder's exact format and makes the next
 * sync a no-op, restores are saves too.
 */
class MapStoryEditingTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = MapStoryFixture::directory();
        Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    /** Write the fixture as the builder would (one-space indent) and sync it. */
    private function synced(?array $doc = null): MapStory
    {
        $doc ??= MapStoryFixture::v2Document();
        file_put_contents($this->dir.'/'.$doc['slug'].'.json', MapStoryFile::encode(MapStoryFile::fromArray($doc)));
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();

        return MapStory::query()->where('slug', $doc['slug'])->sole();
    }

    private function sync(string ...$options): void
    {
        $this->artisan('map-stories:sync', ['--path' => $this->dir, ...array_fill_keys($options, true)])->run();
    }

    private function authored(MapStory $story): stdClass
    {
        return MapStoryFile::authored($story->fresh()->document);
    }

    private function save(MapStory $story, callable $edit, string $source = 'admin', ?User $user = null): array
    {
        $doc = $this->authored($story);
        $edit($doc);

        return app(SaveMapStoryAction::class)($story->fresh(), $doc, $source, $user?->id, 'test edit');
    }

    public function test_the_committed_stories_round_trip_byte_for_byte(): void
    {
        foreach (glob(resource_path('map-stories/*.json')) as $path) {
            $raw = (string) file_get_contents($path);
            $this->assertSame($raw, MapStoryFile::encode(MapStoryFile::decode($raw)), basename($path));
        }
    }

    public function test_authored_drops_only_the_resolved_ids(): void
    {
        $story = $this->synced();
        $stored = $story->document;
        $this->assertObjectHasProperty('entity_id', $stored->entity);
        $this->assertObjectHasProperty('entity_id', $stored->units[0]);

        $authored = MapStoryFile::authored($stored);
        $this->assertObjectNotHasProperty('entity_id', $authored->entity);
        $this->assertObjectNotHasProperty('entity_id', $authored->units[0]);
        $this->assertSame(file_get_contents($this->dir.'/battle-of-testfield.json'), MapStoryFile::encode($authored));
    }

    public function test_a_save_writes_a_revision_and_marks_the_story_edited(): void
    {
        $story = $this->synced();
        $user = User::factory()->create();
        $this->assertFalse($story->isEdited());
        $this->assertSame(1, $story->revisions()->count(), 'the first sync is a revision');

        $result = $this->save($story, fn (stdClass $d) => $d->steps[0]->narrative = 'The armies deploy at dawn beside the river.', user: $user);

        $this->assertSame([], $result['errors']);
        $story->refresh();
        $this->assertTrue($story->isEdited());
        $this->assertSame($user->id, $story->edited_by);
        $this->assertSame('The armies deploy at dawn beside the river.', $story->document->steps[0]->narrative);
        $this->assertSame(['admin', 'import'], $story->revisions()->pluck('source')->all());
        $this->assertSame(1, MapStory::query()->edited()->count());
    }

    public function test_errors_block_a_save_and_write_nothing(): void
    {
        $story = $this->synced();

        $result = $this->save($story, fn (stdClass $d) => $d->units[0]->kind = 'dragons');

        $this->assertNotEmpty($result['errors']);
        $this->assertStringContainsString("'dragons'", implode(' ', $result['errors']));
        $this->assertSame(1, $story->revisions()->count());
        $this->assertFalse($story->fresh()->isEdited());
    }

    public function test_a_story_keeps_its_slug(): void
    {
        $story = $this->synced();

        $result = $this->save($story, fn (stdClass $d) => $d->slug = 'battle-of-elsewhere');

        $this->assertStringContainsString('keeps its slug', implode(' ', $result['errors']));
    }

    public function test_warnings_come_back_but_do_not_block(): void
    {
        $story = $this->synced();

        // Teleport the cavalry 5 km in the second step without an arrow.
        $result = $this->save($story, function (stdClass $d): void {
            $d->steps[1]->moves = [];
            $d->steps[1]->positions->{'blue-horse'} = (object) ['at' => [16.19, 41.31]];
        });

        $this->assertSame([], $result['errors']);
        $this->assertNotEmpty(array_filter($result['warnings'], fn (string $w) => str_contains($w, 'blue-horse moves') && str_contains($w, 'no move arrow')));
    }

    public function test_untouched_floats_keep_their_format_through_a_javascript_round_trip(): void
    {
        $doc = MapStoryFixture::v2Document();
        $doc['steps'][0]['positions']['red-foot']['facing'] = 20.0;
        $story = $this->synced($doc);

        // What the editor sends back: JSON.stringify writes 20.0 as 20.
        $roundTripped = MapStoryFile::decode(str_replace('"facing": 20.0', '"facing": 20', json_encode($this->authored($story), MapStoryFile::JSON_FLAGS | JSON_PRETTY_PRINT)));
        $this->assertSame(20, $roundTripped->steps[0]->positions->{'red-foot'}->facing);
        app(SaveMapStoryAction::class)($story, $roundTripped, 'admin');

        $this->assertSame(20.0, $story->fresh()->document->steps[0]->positions->{'red-foot'}->facing);
    }

    public function test_revisions_are_pruned_to_the_newest_fifty(): void
    {
        $story = $this->synced();
        for ($i = 0; $i < MapStoryRevision::MAX_PER_STORY + 3; $i++) {
            $this->save($story, fn (stdClass $d) => $d->outcome = "The red army wins, take {$i}.");
        }

        $this->assertSame(MapStoryRevision::MAX_PER_STORY, $story->revisions()->count());
        $this->assertSame('The red army wins, take 52.', $story->revisions()->first()->document->outcome);
    }

    public function test_restoring_the_file_version_makes_the_story_clean_again(): void
    {
        $story = $this->synced();
        $original = $story->revisions()->sole();
        $this->save($story, fn (stdClass $d) => $d->title = 'Battle of Testfield (edited)');
        $this->assertTrue($story->fresh()->isEdited());

        $result = app(RestoreMapStoryRevisionAction::class)($story->fresh(), $original);

        $this->assertSame([], $result['errors']);
        $story->refresh();
        $this->assertSame('Battle of Testfield', $story->title);
        $this->assertFalse($story->isEdited(), 'the restored document is what the file holds');
        $this->assertSame('restore', $story->revisions()->first()->source);
        $this->assertSame(file_get_contents($this->dir.'/battle-of-testfield.json'), MapStoryFile::encode($this->authored($story)));
    }

    public function test_sync_skips_an_unchanged_file(): void
    {
        $story = $this->synced();

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('unchanged')
            ->assertSuccessful();
        $this->assertSame(1, $story->revisions()->count());
    }

    public function test_sync_updates_a_changed_file_when_the_row_was_not_edited(): void
    {
        $doc = MapStoryFixture::v2Document();
        $story = $this->synced($doc);
        $doc['outcome'] = 'The blue army wins after all.';
        file_put_contents($this->dir.'/battle-of-testfield.json', MapStoryFile::encode(MapStoryFile::fromArray($doc)));

        $this->sync();

        $this->assertSame('The blue army wins after all.', $story->fresh()->document->outcome);
        $this->assertSame(['sync', 'import'], $story->revisions()->pluck('source')->all());
    }

    public function test_sync_keeps_admin_edits_when_the_file_changed_unless_forced(): void
    {
        $doc = MapStoryFixture::v2Document();
        $story = $this->synced($doc);
        $this->save($story, fn (stdClass $d) => $d->title = 'Edited in the admin');
        $doc['outcome'] = 'A builder change.';
        file_put_contents($this->dir.'/battle-of-testfield.json', MapStoryFile::encode(MapStoryFile::fromArray($doc)));

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain('kept admin edits — export first or use --force')
            ->assertSuccessful();
        $this->assertSame('Edited in the admin', $story->fresh()->title);

        $this->sync('--force');
        $story->refresh();
        $this->assertSame('Battle of Testfield', $story->title);
        $this->assertSame('A builder change.', $story->document->outcome);
        $this->assertFalse($story->isEdited());
        $this->assertSame('Edited in the admin', $story->revisions()->get()[1]->document->title, 'the overwritten edit is a revision');
    }

    public function test_export_writes_the_builder_format_and_the_next_sync_is_a_no_op(): void
    {
        $story = $this->synced();
        $this->save($story, fn (stdClass $d) => $d->steps[1]->title = 'The clash at the ford');

        $this->artisan('map-stories:export', ['--edited' => true, '--path' => $this->dir])
            ->expectsOutputToContain('written')
            ->assertSuccessful();

        $raw = (string) file_get_contents($this->dir.'/battle-of-testfield.json');
        $this->assertStringStartsWith("{\n \"schema\": 2,\n \"slug\": \"battle-of-testfield\",", $raw);
        $this->assertStringEndsWith("}\n", $raw);
        $this->assertStringContainsString('"title": "The clash at the ford"', $raw);
        $this->assertStringNotContainsString('entity_id', $raw);
        $story->refresh();
        $this->assertFalse($story->isEdited());
        $this->assertSame(sha1($raw), $story->file_hash);

        $this->artisan('map-stories:sync', ['--path' => $this->dir])->expectsOutputToContain('unchanged')->assertSuccessful();
        $this->artisan('map-stories:export', ['--edited' => true, '--path' => $this->dir])->expectsOutputToContain('Nothing to export')->assertSuccessful();
    }

    public function test_patch_applies_all_or_nothing(): void
    {
        $story = $this->synced();
        $patch = app(PatchMapStoryAction::class);

        $rejected = $patch($story, [
            ['op' => 'replace', 'path' => '/title', 'value' => 'Half-applied'],
            ['op' => 'replace', 'path' => '/steps/9/title', 'value' => 'No such step'],
        ], 'ai');
        $this->assertStringContainsString('op 1 (replace /steps/9/title)', $rejected['errors'][0]);
        $this->assertSame('Battle of Testfield', $story->fresh()->title);

        $invalid = $patch($story, [['op' => 'replace', 'path' => '/units/0/side', 'value' => 'green']], 'ai');
        $this->assertStringContainsString("unknown side 'green'", implode(' ', $invalid['errors']));
        $this->assertSame(1, $story->revisions()->count());

        $ok = $patch($story, [
            ['op' => 'test', 'path' => '/title', 'value' => 'Battle of Testfield'],
            ['op' => 'replace', 'path' => '/steps/0/title', 'value' => 'The armies deploy'],
            ['op' => 'add', 'path' => '/steps/1/notes/-', 'value' => ['at' => [16.131, 41.304], 'text' => 'The horse charge', 'kind' => 'event']],
        ], 'ai', note: 'clearer titles');
        $this->assertSame([], $ok['errors']);
        $story->refresh();
        $this->assertSame('The armies deploy', $story->document->steps[0]->title);
        $this->assertCount(2, $story->document->steps[1]->notes);
        $this->assertSame(['ai', 'clearer titles'], [$story->revisions()->first()->source, $story->revisions()->first()->note]);
    }

    public function test_a_chronicle_layer_and_a_v3_story_save_with_their_references(): void
    {
        Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['name' => 'Plague of Testland', 'wikidata_id' => 'Q42005']);
        $story = $this->synced(MapStoryFixture::v3Document());

        $result = $this->save($story, fn (stdClass $d) => $d->steps[2]->features->{'sea-lane'}->state = 'recovered');

        $this->assertSame([], $result['errors']);
        $this->assertSame('recovered', $story->fresh()->document->steps[2]->features->{'sea-lane'}->state);
        $this->assertNotEmpty($story->fresh()->ambient_steps);
    }
}
