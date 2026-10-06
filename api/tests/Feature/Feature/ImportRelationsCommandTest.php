<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ImportRelationsCommandTest extends TestCase
{
    use RefreshDatabase;

    /**
     * @param  list<array<string, mixed>>  $records
     */
    private function writeRelationsFile(array $records): string
    {
        $path = sys_get_temp_dir().DIRECTORY_SEPARATOR.'import_relations_'.uniqid('', true).'.jsonl';

        file_put_contents(
            $path,
            implode("\n", array_map(
                static fn (array $r): string => json_encode($r, JSON_THROW_ON_ERROR),
                $records,
            ))."\n",
        );

        $this->beforeApplicationDestroyed(function () use ($path): void {
            if (is_file($path)) {
                unlink($path);
            }
        });

        return $path;
    }

    private function makeEntity(string $name, string $type, string $group): Entity
    {
        return Entity::factory()->create([
            'name' => $name,
            'entity_type' => $type,
            'entity_group' => $group,
        ]);
    }

    public function test_creates_relationship_resolving_both_ends_by_name(): void
    {
        $alex = $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $issus = $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'victorious_at',
            'start_date' => '-0333',
            'description' => 'Decisive victory.',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path, '--batch-id' => 'rel-test'])
            ->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $alex->entity_id,
            'target_entity_id' => $issus->entity_id,
            'relationship_type' => 'victorious_at',
        ]);
    }

    public function test_resolves_names_case_insensitively(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'alexander the great',
            'target_name' => 'BATTLE OF ISSUS',
            'relationship_type' => 'victorious_at',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertSame(1, DB::table('relationships')->where('relationship_type', 'victorious_at')->count());
    }

    public function test_is_idempotent_on_rerun(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'victorious_at',
        ]]);

        $cmd = ['path' => $path, '--batch-id' => 'rel-rerun'];
        $this->artisan('pipeline:import-relations', $cmd)->assertExitCode(0);
        $this->artisan('pipeline:import-relations', $cmd)->assertExitCode(0);

        $this->assertSame(1, DB::table('relationships')->where('relationship_type', 'victorious_at')->count());
    }

    public function test_unresolved_target_creates_no_row_but_succeeds(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Some Entity That Does Not Exist',
            'relationship_type' => 'victorious_at',
        ]]);

        // Unresolved is a data gap, not a fault: exit 0, no row.
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->count());
    }

    public function test_invalid_relationship_type_is_skipped(): void
    {
        $this->makeEntity('Alexander the Great', 'person', 'POLITY');
        $this->makeEntity('Battle of Issus', 'event_battle', 'EVENT');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Alexander the Great',
            'target_name' => 'Battle of Issus',
            'relationship_type' => 'not_a_real_type',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->count());
    }

    private function addAlias(Entity $entity, string $alias): void
    {
        DB::table('entity_aliases')->insert([
            'alias_id' => (string) Str::uuid(),
            'entity_id' => $entity->entity_id,
            'name' => $alias,
            'is_primary' => false,
        ]);
    }

    public function test_resolves_end_by_entity_id_even_when_name_differs(): void
    {
        $franks = $this->makeEntity('Kingdom of the Franks', 'political_entity', 'POLITY');
        $paris = $this->makeEntity('Paris', 'city', 'PLACE');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Paris',
            'target_name' => 'Franks',
            'target_entity_id' => $franks->entity_id,
            'relationship_type' => 'part_of',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $paris->entity_id,
            'target_entity_id' => $franks->entity_id,
            'relationship_type' => 'part_of',
        ]);
    }

    public function test_resolves_end_by_wikidata_id_when_row_was_merged_under_other_name(): void
    {
        // "Eighteenth Dynasty of Egypt" was imported with Q146055 and collapsed into the existing "Eighteenth Dynasty" row.
        $dynasty = Entity::factory()->create([
            'name' => 'Eighteenth Dynasty', 'entity_type' => 'city', 'entity_group' => 'PLACE', 'wikidata_id' => 'Q146055',
        ]);
        $assyria = $this->makeEntity('Neo-Assyrian Empire', 'political_entity', 'POLITY');

        $path = $this->writeRelationsFile([[
            'source_name' => 'Eighteenth Dynasty of Egypt',
            'source_wikidata_id' => 'Q146055',
            'target_name' => 'Neo-Assyrian Empire',
            'relationship_type' => 'part_of',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $dynasty->entity_id,
            'target_entity_id' => $assyria->entity_id,
        ]);
    }

    public function test_entities_file_backfills_qid_for_legacy_records(): void
    {
        $dynasty = Entity::factory()->create([
            'name' => 'Eighteenth Dynasty', 'entity_type' => 'city', 'entity_group' => 'PLACE', 'wikidata_id' => 'Q146055',
        ]);
        $assyria = $this->makeEntity('Neo-Assyrian Empire', 'political_entity', 'POLITY');

        // Legacy relations.jsonl: names only.
        $path = $this->writeRelationsFile([[
            'source_name' => 'Eighteenth Dynasty of Egypt',
            'target_name' => 'Neo-Assyrian Empire',
            'relationship_type' => 'part_of',
        ]]);
        $entities = $this->writeRelationsFile([[
            'name' => 'Eighteenth Dynasty of Egypt', 'entity_type' => 'city', 'wikidata_id' => 'Q146055',
        ]]);

        // Without the sidecar the legacy record misses…
        $this->artisan('pipeline:import-relations', ['path' => $path])->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->count());

        // …with it, the QID finds the merged row.
        $this->artisan('pipeline:import-relations', ['path' => $path, '--entities-file' => $entities])
            ->assertExitCode(0);
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $dynasty->entity_id,
            'target_entity_id' => $assyria->entity_id,
        ]);
    }

    public function test_resolves_end_by_unique_alias_but_not_ambiguous_alias(): void
    {
        $etruscans = $this->makeEntity('Etruscan civilization', 'archaeological_culture', 'CULTURE');
        $this->addAlias($etruscans, 'Etruscans');
        $rome = $this->makeEntity('Rome', 'city', 'PLACE');
        $a = $this->makeEntity('Thebes (Egypt)', 'city', 'PLACE');
        $b = $this->makeEntity('Thebes (Greece)', 'city', 'PLACE');
        $this->addAlias($a, 'Thebes');
        $this->addAlias($b, 'Thebes');

        $path = $this->writeRelationsFile([
            ['source_name' => 'etruscans', 'target_name' => 'Rome', 'relationship_type' => 'influenced_by'],
            ['source_name' => 'Thebes', 'target_name' => 'Rome', 'relationship_type' => 'allied_with'],
        ]);

        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain('RELATION_UNRESOLVED ["Thebes (alias ambiguous)"]')
            ->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $etruscans->entity_id,
            'target_entity_id' => $rome->entity_id,
            'relationship_type' => 'influenced_by',
        ]);
        $this->assertSame(1, DB::table('relationships')->count());
    }

    public function test_logs_each_unresolved_name_with_reason(): void
    {
        $this->makeEntity('Rome', 'city', 'PLACE');

        $path = $this->writeRelationsFile([
            ['source_name' => 'Dendra', 'target_name' => 'Rome', 'relationship_type' => 'part_of'],
            ['source_name' => 'Dendra', 'target_name' => 'Rome', 'relationship_type' => 'allied_with'],
            ['source_name' => 'Rome', 'target_name' => 'Gosan-ni', 'target_wikidata_id' => 'Q1',
                'relationship_type' => 'part_of'],
        ]);

        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain('"unresolved":3')
            ->expectsOutputToContain(
                'RELATION_UNRESOLVED ["Dendra (no entity/alias named it)","Gosan-ni (wikidata_id Q1 not in DB; no entity/alias named it)"]'
            )
            ->assertExitCode(0);
    }

    public function test_skips_self_loop_after_identity_merge(): void
    {
        $dynasty = Entity::factory()->create([
            'name' => 'Eighteenth Dynasty', 'entity_type' => 'city', 'entity_group' => 'PLACE', 'wikidata_id' => 'Q146055',
        ]);

        $path = $this->writeRelationsFile([[
            'source_name' => 'Eighteenth Dynasty of Egypt',
            'source_wikidata_id' => 'Q146055',
            'target_name' => 'Eighteenth Dynasty',
            'relationship_type' => 'part_of',
        ]]);

        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain('"self_loops":1')
            ->assertExitCode(0);
        $this->assertSame(0, DB::table('relationships')->where('source_entity_id', $dynasty->entity_id)->count());
    }

    public function test_additive_recovery_resolves_name_first_and_only_fills_gaps(): void
    {
        // The original name-keyed import linked "Kush" (a duplicate row); the QID
        // now points at "Kingdom of Kush". Recovery must not add a second copy.
        $kush = $this->makeEntity('Kush', 'political_entity', 'POLITY');
        $kingdom = Entity::factory()->create([
            'name' => 'Kingdom of Kush', 'entity_type' => 'political_entity', 'entity_group' => 'POLITY',
            'wikidata_id' => 'Q241790',
        ]);
        $egypt = $this->makeEntity('Egypt', 'political_entity', 'POLITY');
        $dynasty = Entity::factory()->create([
            'name' => 'Eighteenth Dynasty', 'entity_type' => 'city', 'entity_group' => 'PLACE', 'wikidata_id' => 'Q146055',
        ]);
        DB::table('relationships')->insert([
            'source_entity_id' => $kush->entity_id, 'target_entity_id' => $egypt->entity_id,
            'relationship_type' => 'at_war_with', 'confidence' => 'medium', 'created_at' => now(),
        ]);

        $path = $this->writeRelationsFile([
            ['source_name' => 'Kush', 'source_wikidata_id' => 'Q241790', 'target_name' => 'Egypt',
                'relationship_type' => 'at_war_with'],
            // Genuinely missing (name never resolved): recovery adds it via the QID.
            ['source_name' => 'Eighteenth Dynasty of Egypt', 'source_wikidata_id' => 'Q146055', 'target_name' => 'Egypt',
                'relationship_type' => 'at_war_with'],
        ]);

        $this->artisan('pipeline:import-relations', ['path' => $path, '--additive-recovery' => true])
            ->expectsOutputToContain('"created":1,"skipped":1')
            ->assertExitCode(0);

        $this->assertSame(0, DB::table('relationships')->where('source_entity_id', $kingdom->entity_id)->count());
        $this->assertSame(1, DB::table('relationships')->where('source_entity_id', $dynasty->entity_id)->count());
        $this->assertSame(2, DB::table('relationships')->count());
    }

    public function test_rejects_a_wikidata_hit_whose_row_name_is_incompatible(): void
    {
        // The pipeline gave "World War I" World War II's QID; following it would
        // attach WWI facts to the WWII row. The guard rejects it and the name
        // resolves the real row instead.
        $ww2 = Entity::factory()->create([
            'name' => 'World War II', 'entity_type' => 'event_war', 'entity_group' => 'EVENT', 'wikidata_id' => 'Q362',
        ]);
        $ww1 = $this->makeEntity('World War I', 'event_war', 'EVENT');
        $france = $this->makeEntity('France', 'political_entity', 'POLITY');

        $path = $this->writeRelationsFile([
            ['source_name' => 'France', 'target_name' => 'World War I', 'target_wikidata_id' => 'Q362',
                'relationship_type' => 'participated_in'],
            ['source_name' => 'France', 'target_name' => 'Great War', 'target_wikidata_id' => 'Q362',
                'relationship_type' => 'fought_at'],
        ]);

        $this->artisan('pipeline:import-relations', ['path' => $path])
            ->expectsOutputToContain("Great War (wikidata_id Q362 is 'World War II' (name mismatch); no entity/alias named it)")
            ->assertExitCode(0);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $france->entity_id, 'target_entity_id' => $ww1->entity_id,
        ]);
        $this->assertSame(0, DB::table('relationships')->where('target_entity_id', $ww2->entity_id)->count());
    }
}
