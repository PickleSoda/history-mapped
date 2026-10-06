<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\VerificationStatus;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Temporal namesake guard across the import layer: bare regnal labels
 * ('Philip II', 'Charles V') must link to the namesake of the right era —
 * relations (pipeline:import-relations), entity dedup (pipeline:import) and
 * chronicle secondary entities (chronicles:import).
 */
class NamesakeGuardImportTest extends TestCase
{
    use RefreshDatabase;

    private function person(string $name, ?string $start, ?string $end, ?string $qid = null, string $createdAt = '2026-10-01 00:00:00'): Entity
    {
        $factory = Entity::factory();
        if ($start !== null && $end !== null) {
            $factory = $factory->withTemporalRange($start, $end);
        }

        return $factory->create([
            'name' => $name,
            'entity_type' => 'person',
            'entity_group' => 'POLITY',
            'wikidata_id' => $qid,
            'summary' => "{$name} ({$start}..{$end})",
            'created_at' => $createdAt,
        ]);
    }

    private function polity(string $name): Entity
    {
        return Entity::factory()->create(['name' => $name, 'entity_type' => 'political_entity', 'entity_group' => 'POLITY']);
    }

    /**
     * @param  list<array<string, mixed>>  $records
     */
    private function jsonl(array $records): string
    {
        $path = sys_get_temp_dir().DIRECTORY_SEPARATOR.'namesake_'.uniqid('', true).'.jsonl';
        file_put_contents($path, implode("\n", array_map(static fn (array $r): string => json_encode($r, JSON_THROW_ON_ERROR), $records))."\n");
        $this->beforeApplicationDestroyed(static function () use ($path): void {
            if (is_file($path)) {
                unlink($path);
            }
        });

        return $path;
    }

    private function relationSource(string $targetName, string $type = 'rules'): ?string
    {
        $value = DB::table('relationships as r')
            ->join('entities as t', 't.entity_id', '=', 'r.target_entity_id')
            ->where('t.name', $targetName)
            ->where('r.relationship_type', $type)
            ->value('r.source_entity_id');

        return $value === null ? null : (string) $value;
    }

    // ── relations ───────────────────────────────────────────────────────────

    public function test_relation_links_the_namesake_of_its_era(): void
    {
        $macedon = $this->person('Philip II', '-382', '-336', 'Q130650', '2026-10-01 00:00:00');
        $spain = $this->person('Philip II', '1527', '1598', 'Q83229', '2026-10-02 00:00:00');
        $this->polity('Spain');
        $this->polity('Macedonia');

        $path = $this->jsonl([
            ['source_name' => 'Philip II', 'target_name' => 'Spain', 'relationship_type' => 'rules', 'start_date' => '1556', 'end_date' => '1598'],
            ['source_name' => 'Philip II', 'target_name' => 'Macedonia', 'relationship_type' => 'rules', 'start_date' => '-359', 'end_date' => '-336'],
        ]);
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame($spain->entity_id, $this->relationSource('Spain'));
        $this->assertSame($macedon->entity_id, $this->relationSource('Macedonia'));
    }

    public function test_relation_refuses_a_lone_namesake_of_another_era(): void
    {
        $this->person('Philip II', '-382', '-336', 'Q130650');
        $this->polity('Viceroyalty of Peru');

        $path = $this->jsonl([[
            'source_name' => 'Philip II', 'target_name' => 'Viceroyalty of Peru', 'relationship_type' => 'rules',
            'start_date' => '1556', 'source_wikidata_id' => 'Q130650',
        ]]);
        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain('"unresolved":1')
            ->expectsOutputToContain('Philip II (wikidata_id Q130650 is \'Philip II\' of another era (-382..-336 vs 1556); namesake_ambiguous')
            ->assertExitCode(0);

        $this->assertSame(0, DB::table('relationships')->count());
    }

    public function test_relation_falls_back_to_an_alias_of_the_right_era(): void
    {
        $this->person('Philip II', '-382', '-336');
        $spain = $this->person('Philip II of Spain', '1527', '1598');
        DB::table('entity_aliases')->insert([
            'alias_id' => (string) Str::uuid(), 'entity_id' => $spain->entity_id, 'name' => 'Philip II', 'is_primary' => false,
        ]);
        $this->polity('New Spain');

        $path = $this->jsonl([['source_name' => 'Philip II', 'target_name' => 'New Spain', 'relationship_type' => 'rules', 'start_date' => '1556']]);
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame($spain->entity_id, $this->relationSource('New Spain'));
    }

    public function test_charles_v_qid_of_the_french_king_does_not_rule_the_hre(): void
    {
        $this->person('Charles V', '1338', '1380', 'Q167782', '2026-10-01 00:00:00');
        $hre = $this->person('Charles V', '1500', '1558', null, '2026-10-02 00:00:00');
        $this->polity('Holy Roman Empire');

        $path = $this->jsonl([[
            'source_name' => 'Charles V', 'target_name' => 'Holy Roman Empire', 'relationship_type' => 'rules',
            'start_date' => '1519', 'source_wikidata_id' => 'Q167782',
        ]]);
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame($hre->entity_id, $this->relationSource('Holy Roman Empire'));
    }

    public function test_undated_relation_between_dated_namesakes_stays_unresolved(): void
    {
        $this->person('Philip II', '-382', '-336');
        $this->person('Philip II', '1527', '1598');
        $this->polity('Spain');

        $path = $this->jsonl([['source_name' => 'Philip II', 'target_name' => 'Spain', 'relationship_type' => 'rules']]);
        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain('"unresolved":1')
            ->expectsOutputToContain('namesake_ambiguous: 2 \'Philip II\' rows of different eras')
            ->assertExitCode(0);
    }

    public function test_same_person_with_slightly_different_dates_still_links(): void
    {
        $spain = $this->person('Philip II', '1527', '1598');
        $this->polity('Portugal');

        // Dated two years after his death (a reign end mis-dated): within tolerance.
        $path = $this->jsonl([['source_name' => 'Philip II', 'target_name' => 'Portugal', 'relationship_type' => 'rules', 'start_date' => '1580', 'end_date' => '1600']]);
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame($spain->entity_id, $this->relationSource('Portugal'));
    }

    public function test_posthumous_relation_types_are_not_date_checked(): void
    {
        $aristotle = $this->person('Aristotle', '-384', '-322');
        $aquinas = $this->person('Thomas Aquinas', '1225', '1274');

        $path = $this->jsonl([['source_name' => 'Thomas Aquinas', 'target_name' => 'Aristotle', 'relationship_type' => 'influenced_by', 'start_date' => '1260']]);
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertDatabaseHas('relationships', ['source_entity_id' => $aquinas->entity_id, 'target_entity_id' => $aristotle->entity_id]);
    }

    // ── entity import ───────────────────────────────────────────────────────

    /**
     * @param  array<string, mixed>  $record
     */
    private function importEntity(array $record, bool $force = false): void
    {
        $this->artisan('pipeline:import', [
            'path' => $this->jsonl([$record + ['entity_type' => 'person', 'entity_group' => 'POLITY', 'summary' => 's']]),
            '--sync' => true,
            '--skip-relationships' => true,
            '--force' => $force,
        ])->assertExitCode(0);
    }

    public function test_entity_of_another_era_is_not_skipped_as_a_duplicate(): void
    {
        $macedon = $this->person('Philip II', '-382', '-336', 'Q130650');

        $this->importEntity(['name' => 'Philip II', 'temporal_start' => '1527', 'temporal_end' => '1598', 'summary' => 'King of Spain']);

        $this->assertSame(2, Entity::query()->where('name', 'Philip II')->count());
        $new = Entity::query()->where('name', 'Philip II')->whereKeyNot($macedon->entity_id)->firstOrFail();
        $this->assertSame(VerificationStatus::NeedsReview, $new->verification_status);
        $this->assertContains('namesake_ambiguous', $new->getAttribute('attributes')['validation_flags'] ?? []);
    }

    public function test_namesake_qid_never_merges_spanish_content_into_the_macedonian_row(): void
    {
        $macedon = $this->person('Philip II', '-382', '-336', 'Q130650');

        // The pipeline gave the Spanish king the Macedonian's QID; --force would
        // otherwise overwrite the Macedonian row with Spanish content.
        $this->importEntity([
            'name' => 'Philip II', 'wikidata_id' => 'Q130650', 'temporal_start' => '1527', 'temporal_end' => '1598',
            'summary' => 'King of Spain who sent the Armada.',
        ], force: true);

        $macedon->refresh();
        $this->assertSame('Philip II (-382..-336)', $macedon->summary);
        $new = Entity::query()->where('name', 'Philip II')->whereKeyNot($macedon->entity_id)->firstOrFail();
        $this->assertNull($new->wikidata_id);
        $this->assertSame('Q130650', $new->getAttribute('attributes')['_rejected_wikidata_id'] ?? null);
        $this->assertSame(VerificationStatus::NeedsReview, $new->verification_status);
        $this->assertSame(1, Entity::query()->where('wikidata_id', 'Q130650')->count());
    }

    public function test_same_person_with_slightly_different_dates_merges(): void
    {
        $this->person('Philip II', '-382', '-336');
        $spain = $this->person('Philip II', '1527', '1598');

        // Reign dates; then a single date two years after his death.
        $this->importEntity(['name' => 'Philip II', 'temporal_start' => '1556', 'temporal_end' => '1598']);
        $this->importEntity(['name' => 'Philip II', 'temporal_start' => '1600']);

        $this->assertSame(2, Entity::query()->where('name', 'Philip II')->count());
        $this->assertSame('Philip II (1527..1598)', $spain->refresh()->summary);
    }

    public function test_undated_record_uses_the_pipeline_identity_span(): void
    {
        $macedon = $this->person('Philip II', '-382', '-336');
        $spain = $this->person('Philip II', '1527', '1598');

        // Undated but its relations date it to 1556-1598: the Spanish row → duplicate.
        $this->importEntity(['name' => 'Philip II', '_identity_span' => [1556, 1598]]);
        $this->assertSame(2, Entity::query()->where('name', 'Philip II')->count());

        // Undated with no span between two dated namesakes: a new row for review.
        $this->importEntity(['name' => 'Philip II']);
        $this->assertSame(3, Entity::query()->where('name', 'Philip II')->count());
        $new = Entity::query()->where('name', 'Philip II')->whereKeyNot([$macedon->entity_id, $spain->entity_id])->firstOrFail();
        $this->assertSame(VerificationStatus::NeedsReview, $new->verification_status);
        $this->assertArrayNotHasKey('_identity_span', $new->getAttribute('attributes') ?? []);
    }

    // ── chronicles ──────────────────────────────────────────────────────────

    public function test_chronicle_entry_links_the_namesake_of_its_era(): void
    {
        $this->person('Charles V', '1338', '1380', 'Q167782', '2026-10-01 00:00:00');
        $hre = $this->person('Charles V', '1500', '1558', null, '2026-10-02 00:00:00');

        $path = storage_path('app/testing/'.uniqid('namesake_', true).'/chronicle.json');
        File::ensureDirectoryExists(dirname($path));
        File::put($path, json_encode([
            'title' => 'Reformation', 'slug' => 'namesake-chronicle',
            'entries' => [[
                'sequence_order' => 0, 'start_year' => 1521, 'end_year' => 1521,
                'narrative_text' => 'Charles V presided over the Diet of Worms.',
                'secondary_entities' => [['entity_id' => 'Charles V', 'name' => 'Charles V', 'wikidata_id' => 'Q167782']],
            ]],
        ], JSON_PRETTY_PRINT));
        $this->beforeApplicationDestroyed(fn () => File::deleteDirectory(dirname($path)));

        $this->artisan('chronicles:import', ['path' => $path])->assertExitCode(0);

        $entry = ChronicleEntry::firstOrFail();
        $this->assertSame([$hre->entity_id], $entry->secondaryEntities()->pluck('entities.entity_id')->all());
    }
}
