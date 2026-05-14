<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ImportBorderRelationsCommandTest extends TestCase
{
    use RefreshDatabase;

    /**
     * @param  list<array<string, mixed>>  $entities
     * @param  list<array<string, mixed>>  $hints
     */
    private function writeRelationImportDir(array $entities, array $hints): string
    {
        $dir = sys_get_temp_dir().DIRECTORY_SEPARATOR.'import_border_relations_'.uniqid('', true);
        mkdir($dir, 0777, true);

        file_put_contents(
            $dir.DIRECTORY_SEPARATOR.'ohm_relation_entities.jsonl',
            implode("\n", array_map(static fn (array $record): string => json_encode($record, JSON_THROW_ON_ERROR), $entities))."\n",
        );

        file_put_contents(
            $dir.DIRECTORY_SEPARATOR.'ohm_relation_hints.jsonl',
            implode("\n", array_map(static fn (array $record): string => json_encode($record, JSON_THROW_ON_ERROR), $hints))."\n",
        );

        $this->beforeApplicationDestroyed(function () use ($dir): void {
            foreach (glob($dir.DIRECTORY_SEPARATOR.'*') ?: [] as $path) {
                if (is_file($path)) {
                    unlink($path);
                }
            }

            if (is_dir($dir)) {
                rmdir($dir);
            }
        });

        return $dir;
    }

    /**
     * @return array<string, mixed>
     */
    private function relationEntityRecord(array $overrides = []): array
    {
        return array_replace_recursive([
            'name' => 'Old Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q090',
            'summary' => 'Former polity.',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
            'source_citations' => [['source' => 'wikidata', 'wikidata_id' => 'Q090']],
        ], $overrides);
    }

    /**
     * @return array<string, mixed>
     */
    private function relationHintRecord(array $overrides = []): array
    {
        return array_replace_recursive([
            'source_wikidata_id' => 'Q100',
            'source_name' => 'Kingdom of Testland',
            'relationship_type' => 'preceded_by',
            'target_wikidata_id' => 'Q090',
            'target_label' => 'Old Testland',
            'temporal_start' => null,
            'temporal_end' => null,
            'confidence' => 'medium',
            'source' => 'wikidata:P155',
        ], $overrides);
    }

    public function test_command_imports_relation_entities_and_stages_hints(): void
    {
        $source = Entity::factory()->create([
            'name' => 'Kingdom of Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q100',
        ]);

        $dir = $this->writeRelationImportDir(
            [$this->relationEntityRecord()],
            [$this->relationHintRecord()],
        );

        $this->artisan('pipeline:import-border-relations', [
            'path' => $dir,
            '--sync' => true,
            '--skip-resolve' => true,
            '--batch-id' => 'border-rel-test',
        ])->assertExitCode(0);

        $target = Entity::query()->where('wikidata_id', 'Q090')->first();
        $this->assertNotNull($target);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'source_entity_id' => $source->entity_id,
            'relationship_type' => 'preceded_by',
            'target_wikidata_id' => 'Q090',
            'target_label' => 'Old Testland',
            'batch_id' => 'border-rel-test',
            'resolved' => false,
        ]);
    }

    public function test_command_optionally_resolves_relationships(): void
    {
        $source = Entity::factory()->create([
            'name' => 'Kingdom of Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q100',
        ]);

        $dir = $this->writeRelationImportDir(
            [$this->relationEntityRecord()],
            [$this->relationHintRecord()],
        );

        $this->artisan('pipeline:import-border-relations', [
            'path' => $dir,
            '--sync' => true,
            '--batch-id' => 'border-rel-resolve',
        ])->assertExitCode(0);

        $target = Entity::query()->where('wikidata_id', 'Q090')->firstOrFail();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'preceded_by',
        ]);

        $this->assertDatabaseHas('pipeline_relationship_hints', [
            'source_entity_id' => $source->entity_id,
            'target_wikidata_id' => 'Q090',
            'batch_id' => 'border-rel-resolve',
            'resolved' => true,
        ]);
    }

    public function test_command_is_idempotent_on_rerun_with_same_batch(): void
    {
        Entity::factory()->create([
            'name' => 'Kingdom of Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q100',
        ]);

        $dir = $this->writeRelationImportDir(
            [$this->relationEntityRecord()],
            [$this->relationHintRecord()],
        );

        $command = [
            'path' => $dir,
            '--sync' => true,
            '--batch-id' => 'border-rel-rerun',
        ];

        $this->artisan('pipeline:import-border-relations', $command)->assertExitCode(0);
        $this->artisan('pipeline:import-border-relations', $command)->assertExitCode(0);

        $this->assertCount(1, Entity::query()->where('wikidata_id', 'Q090')->get());
        $this->assertCount(1, EntityRelationship::query()->where('relationship_type', 'preceded_by')->get());
        $this->assertSame(1, DB::table('pipeline_relationship_hints')->where('batch_id', 'border-rel-rerun')->count());
    }
}
