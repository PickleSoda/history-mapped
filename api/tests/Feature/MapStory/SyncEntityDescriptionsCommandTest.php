<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Actions\Entity\SyncEntityDescriptionFileAction;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class SyncEntityDescriptionsCommandTest extends TestCase
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

    private function file(string $name, string $front, string $body): void
    {
        file_put_contents("{$this->dir}/{$name}.md", "---\n{$front}\n---\n{$body}\n");
    }

    private function sync(bool $force = false): int
    {
        return $this->artisan('entities:sync-descriptions', ['--path' => $this->dir, '--force' => $force])->run();
    }

    public function test_sets_descriptions_by_qid_or_unique_name_joining_wrapped_lines(): void
    {
        $cannae = Entity::factory()->create(['name' => 'Battle of Cannae', 'wikidata_id' => 'Q179591']);
        $zama = Entity::factory()->create(['name' => 'Battle of Zama']);
        $this->file('cannae', "wikidata: Q179591\nname: Battle of Cannae", "First line\nwrapped here.\n\n\nSecond paragraph.");
        $this->file('zama', 'name: "Battle of Zama"', 'Only paragraph.');

        $this->assertSame(0, $this->sync());

        $this->assertSame("First line wrapped here.\n\nSecond paragraph.", $cannae->refresh()->description);
        $this->assertSame('Only paragraph.', $zama->refresh()->description);
        $this->assertSame(sha1('Only paragraph.'), $zama->attributes[SyncEntityDescriptionFileAction::SYNC_KEY]);
    }

    public function test_reports_files_it_cannot_place(): void
    {
        Entity::factory()->count(2)->create(['name' => 'Battle of Salamis']);
        $this->file('salamis', 'name: Battle of Salamis', 'Ambiguous name.');
        $this->file('nowhere', 'wikidata: Q1', 'No such entity.');
        file_put_contents("{$this->dir}/broken.md", 'no front matter');

        $this->artisan('entities:sync-descriptions', ['--path' => $this->dir])
            ->expectsOutputToContain('unresolved')
            ->expectsOutputToContain('invalid')
            ->assertFailed();
    }

    public function test_keeps_a_description_edited_since_the_last_sync_unless_forced(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q48314']);
        $this->file('waterloo', 'wikidata: Q48314', 'Synced text.');
        $this->sync();

        // A re-sync of new file text replaces text the sync wrote itself.
        $this->file('waterloo', 'wikidata: Q48314', 'Revised text.');
        $this->sync();
        $this->assertSame('Revised text.', $entity->refresh()->description);

        // An editor's change is kept…
        $entity->update(['description' => 'Editor text.']);
        $this->file('waterloo', 'wikidata: Q48314', 'Third text.');
        $this->artisan('entities:sync-descriptions', ['--path' => $this->dir])
            ->expectsOutputToContain('edited')
            ->assertSuccessful();
        $this->assertSame('Editor text.', $entity->refresh()->description);

        // …until forced.
        $this->sync(force: true);
        $this->assertSame('Third text.', $entity->refresh()->description);
    }
}
