<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ResolvePipelineRelationshipsCommandTest extends TestCase
{
    use RefreshDatabase;

    private function seedHint(Entity $source, string $targetWikidataId, string $type, string $batchId): int
    {
        return DB::table('pipeline_relationship_hints')->insertGetId([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetWikidataId,
            'target_label' => 'Label',
            'batch_id' => $batchId,
            'resolved' => false,
        ]);
    }

    public function test_resolves_single_batch(): void
    {
        $batchId = 'batch-a';
        $source = Entity::factory()->create(['wikidata_id' => 'Q1']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q2']);
        $this->seedHint($source, 'Q2', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])
            ->assertSuccessful();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
        ]);
    }

    public function test_resolves_all_unresolved_batches_when_no_batch_id_given(): void
    {
        $batchA = 'batch-a';
        $batchB = 'batch-b';
        $sourceA = Entity::factory()->create(['wikidata_id' => 'Q10']);
        $sourceB = Entity::factory()->create(['wikidata_id' => 'Q11']);
        $targetA = Entity::factory()->create(['wikidata_id' => 'Q20']);
        $targetB = Entity::factory()->create(['wikidata_id' => 'Q21']);
        $this->seedHint($sourceA, 'Q20', 'part_of', $batchA);
        $this->seedHint($sourceB, 'Q21', 'part_of', $batchB);

        $this->artisan('pipeline:resolve-relationships')
            ->assertSuccessful();

        $this->assertDatabaseCount('relationships', 2);
    }

    public function test_dry_run_does_not_create_relationships(): void
    {
        $batchId = 'batch-c';
        $source = Entity::factory()->create(['wikidata_id' => 'Q30']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q31']);
        $this->seedHint($source, 'Q31', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', [
            'batchId' => $batchId,
            '--dry-run' => true,
        ])->assertSuccessful();

        $this->assertDatabaseCount('relationships', 0);
    }

    public function test_idempotent_rerun(): void
    {
        $batchId = 'batch-d';
        $source = Entity::factory()->create(['wikidata_id' => 'Q40']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q41']);
        $this->seedHint($source, 'Q41', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])->assertSuccessful();
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])->assertSuccessful();

        $this->assertDatabaseCount('relationships', 1);
    }
}