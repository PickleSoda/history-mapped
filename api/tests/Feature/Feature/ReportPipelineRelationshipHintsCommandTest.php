<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ReportPipelineRelationshipHintsCommandTest extends TestCase
{
    use RefreshDatabase;

    private function seedHint(Entity $source, string $targetWikidataId, string $type, string $batchId, bool $resolved = false, ?string $note = null): void
    {
        DB::table('pipeline_relationship_hints')->insert([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetWikidataId,
            'target_label' => 'Label',
            'batch_id' => $batchId,
            'resolved' => $resolved,
            'resolution_note' => $note,
        ]);
    }

    public function test_reports_counts_by_batch(): void
    {
        $batch = 'batch-r';
        $source = Entity::factory()->create();
        $this->seedHint($source, 'Q1', 'part_of', $batch, true, 'created');
        $this->seedHint($source, 'Q2', 'part_of', $batch, false, 'target_not_found');

        $this->artisan('pipeline:report-relationship-hints', ['batchId' => $batch])
            ->assertSuccessful()
            ->expectsOutputToContain('target_not_found');
    }

    public function test_reports_all_batches_when_no_batch_id_given(): void
    {
        $source = Entity::factory()->create();
        $this->seedHint($source, 'Q1', 'part_of', 'batch-a', false, 'target_not_found');
        $this->seedHint($source, 'Q2', 'part_of', 'batch-b', true, 'created');

        $this->artisan('pipeline:report-relationship-hints')
            ->assertSuccessful();
    }

    public function test_handles_empty_table(): void
    {
        $this->artisan('pipeline:report-relationship-hints')
            ->assertSuccessful()
            ->expectsOutputToContain('No hints found');
    }
}
