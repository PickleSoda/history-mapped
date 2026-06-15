<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class PipelineEventHubImportTest extends TestCase
{
    use RefreshDatabase;

    public function test_end_to_end_battle_cluster_import_and_resolution(): void
    {
        $battleId = 'Q12345';
        $armyAId = 'Q111';
        $armyBId = 'Q222';
        $commanderAId = 'Q333';
        $commanderBId = 'Q444';
        $placeId = 'Q555';

        // Seed entities as if imported from JSONL
        $battle = Entity::factory()->create([
            'wikidata_id' => $battleId,
            'name' => 'Battle of Gaugamela',
            'entity_type' => 'event_battle',
        ]);
        $armyA = Entity::factory()->create(['wikidata_id' => $armyAId, 'name' => 'Macedonian Army']);
        $armyB = Entity::factory()->create(['wikidata_id' => $armyBId, 'name' => 'Persian Army']);
        $commanderA = Entity::factory()->create(['wikidata_id' => $commanderAId, 'name' => 'Alexander']);
        $commanderB = Entity::factory()->create(['wikidata_id' => $commanderBId, 'name' => 'Darius III']);
        $place = Entity::factory()->create(['wikidata_id' => $placeId, 'name' => 'Gaugamela']);

        // Stage hints
        $batchId = 'test-battle-cluster';
        $hints = [
            [$armyA->entity_id, $battleId, 'participated_in'],
            [$armyB->entity_id, $battleId, 'participated_in'],
            [$commanderA->entity_id, $armyAId, 'commanded'],
            [$commanderA->entity_id, $battleId, 'victorious_at'],
            [$commanderB->entity_id, $battleId, 'defeated_at'],
            [$battle->entity_id, $placeId, 'located_at'],
        ];

        foreach ($hints as [$sourceId, $targetQid, $type]) {
            DB::table('pipeline_relationship_hints')->insert([
                'source_entity_id' => $sourceId,
                'relationship_type' => $type,
                'target_wikidata_id' => $targetQid,
                'batch_id' => $batchId,
                'resolved' => false,
            ]);
        }

        // Run resolution
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        // Assert graph edges
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $armyA->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'participated_in',
        ]);
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $commanderA->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'victorious_at',
        ]);
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $battle->entity_id,
            'target_entity_id' => $place->entity_id,
            'relationship_type' => 'located_at',
        ]);

        // Assert no hints remain unresolved
        $this->assertDatabaseCount('pipeline_relationship_hints', 6);
        $this->assertDatabaseMissing('pipeline_relationship_hints', [
            'batch_id' => $batchId,
            'resolved' => false,
        ]);
    }

    public function test_late_arriving_target_entity_gets_resolved_on_retry(): void
    {
        $batchId = 'test-late-target';
        $source = Entity::factory()->create(['wikidata_id' => 'Q900']);

        DB::table('pipeline_relationship_hints')->insert([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => 'allied_with',
            'target_wikidata_id' => 'Q999',
            'batch_id' => $batchId,
            'resolved' => false,
        ]);

        // First run: target missing
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        $this->assertDatabaseCount('relationships', 0);

        // Import the missing target
        $target = Entity::factory()->create(['wikidata_id' => 'Q999']);

        // Second run: target now exists
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'allied_with',
        ]);
    }
}
