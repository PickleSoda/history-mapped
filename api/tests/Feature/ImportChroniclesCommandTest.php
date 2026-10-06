<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class ImportChroniclesCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_import_persists_new_fields_and_source_evidence(): void
    {
        $fixturePath = storage_path('app/testing/chronicle.json');

        $fixtureData = [
            'title' => 'Test Chronicle',
            'slug' => 'test-chronicle',
            'source_type' => 'video_transcript',
            'source_reference' => 'ref-123',
            'status' => 'draft',
            'start_year' => -1200,
            'end_year' => -1100,
            'impact_score' => 8,
            'approximate_location' => ['lat' => 30.0, 'lng' => 31.0],
            'metadata' => [],
            'entries' => [
                [
                    'sequence_order' => 0,
                    'narrative_text' => 'Test narrative',
                    'start_year' => -1150,
                    'end_year' => -1140,
                    'impact_score' => 5,
                    'approximate_location' => ['lat' => 30.5, 'lng' => 31.5],
                    'source_evidence' => ['event:0'],
                    'secondary_entities' => [],
                ],
            ],
        ];

        File::ensureDirectoryExists(dirname($fixturePath));
        File::put($fixturePath, json_encode($fixtureData, JSON_PRETTY_PRINT));

        try {
            $this->artisan('chronicles:import', ['path' => $fixturePath, '--force' => true])
                ->assertExitCode(0);

            $chronicle = Chronicle::where('slug', 'test-chronicle')->first();
            $this->assertNotNull($chronicle);
            $this->assertEquals(-1200, $chronicle->start_year);
            $this->assertEquals(-1100, $chronicle->end_year);
            $this->assertEquals(8, $chronicle->impact_score);
            $this->assertEquals(['lat' => 30.0, 'lng' => 31.0], $chronicle->approximate_location);

            $entry = ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->first();
            $this->assertNotNull($entry);
            $this->assertEquals(-1150, $entry->start_year);
            $this->assertEquals(-1140, $entry->end_year);
            $this->assertEquals(5, $entry->impact_score);
            $this->assertEquals(['lat' => 30.5, 'lng' => 31.5], $entry->approximate_location);
            $this->assertEquals(['event:0'], $entry->source_evidence);
        } finally {
            File::delete($fixturePath);
        }
    }

    private function writeChronicle(array $data): string
    {
        $path = storage_path('app/testing/'.uniqid('chron_', true).'/chronicle.json');
        File::ensureDirectoryExists(dirname($path));
        File::put($path, json_encode($data, JSON_PRETTY_PRINT));
        $this->beforeApplicationDestroyed(fn () => File::deleteDirectory(dirname($path)));

        return $path;
    }

    private function entity(string $name, ?string $qid = null): Entity
    {
        return Entity::factory()->create([
            'name' => $name, 'entity_type' => 'city', 'entity_group' => 'PLACE', 'wikidata_id' => $qid,
        ]);
    }

    public function test_secondary_entity_resolves_by_wikidata_id_when_label_misses(): void
    {
        $dynasty = $this->entity('Eighteenth Dynasty', 'Q146055');
        $path = $this->writeChronicle([
            'title' => 'T', 'slug' => 'qid-chronicle',
            'entries' => [[
                'sequence_order' => 0,
                'narrative_text' => 'The Eighteenth Dynasty of Egypt flourished.',
                'secondary_entities' => [
                    ['entity_id' => 'Eighteenth Dynasty of Egypt', 'name' => 'Eighteenth Dynasty of Egypt', 'wikidata_id' => 'Q146055'],
                    ['entity_id' => 'Dendra', 'name' => 'Dendra'],
                ],
            ]],
        ]);

        $this->artisan('chronicles:import', ['path' => $path])
            ->expectsOutputToContain('CHRONICLE_UNRESOLVED ["Dendra (no entity/alias named it)"]')
            ->assertExitCode(0);

        $entry = ChronicleEntry::firstOrFail();
        $this->assertSame([$dynasty->entity_id], $entry->secondaryEntities()->pluck('entities.entity_id')->all());
    }

    public function test_link_missing_only_adds_links_to_existing_entries(): void
    {
        $kept = $this->entity('Rome');
        $missing = $this->entity('Ostia');

        $chronicle = Chronicle::factory()->create(['slug' => 'repair-me', 'status' => 'published', 'title' => 'Original']);
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => 0,
            'narrative_text' => 'Rome founded Ostia.',
        ]);
        $entry->secondaryEntities()->attach([$kept->entity_id => ['role' => 'location']]);

        $path = $this->writeChronicle([
            'title' => 'Rewritten', 'slug' => 'repair-me', 'status' => 'draft',
            'entries' => [
                ['sequence_order' => 0, 'narrative_text' => 'Rome founded Ostia.', 'secondary_entities' => [
                    ['entity_id' => $kept->entity_id, 'role' => 'participant'],
                    ['entity_id' => 'Ostia'],
                ]],
                // Not in the DB: link-missing never creates entries.
                ['sequence_order' => 1, 'narrative_text' => 'A new entry.', 'secondary_entities' => [
                    ['entity_id' => 'Ostia'],
                ]],
            ],
        ]);

        $this->artisan('chronicles:import', ['path' => $path, '--link-missing' => true])
            ->expectsOutputToContain('links added: 1, unmatched entries: 1')
            ->assertExitCode(0);

        $chronicle->refresh();
        $this->assertSame('Original', $chronicle->title);  // metadata untouched
        $this->assertSame(1, ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->count());
        $links = DB::table('chronicle_entry_entities')->where('entry_id', $entry->entry_id)->pluck('role', 'entity_id')->all();
        $this->assertSame(['location', 'participant'], [$links[$kept->entity_id], $links[$missing->entity_id]]);

        // Idempotent: a second pass adds nothing.
        $this->artisan('chronicles:import', ['path' => $path, '--link-missing' => true])
            ->expectsOutputToContain('links added: 0')
            ->assertExitCode(0);
        $this->assertSame(2, DB::table('chronicle_entry_entities')->where('entry_id', $entry->entry_id)->count());
    }

    public function test_link_missing_refuses_force(): void
    {
        $path = $this->writeChronicle(['title' => 'T', 'slug' => 's', 'entries' => []]);

        $this->artisan('chronicles:import', ['path' => $path, '--link-missing' => true, '--force' => true])
            ->assertExitCode(1);
    }
}
