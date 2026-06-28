<?php

declare(strict_types=1);

namespace Tests\Feature\Ai;

use App\Actions\Entity\MergeEntitiesAction;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Mockery\MockInterface;
use Tests\TestCase;

class MergeDuplicateEntitiesToolTest extends TestCase
{
    use RefreshDatabase;

    // ── 1. buildParts returns the correct shape ───────────────────────────────

    public function test_build_parts_returns_single_merge_part_with_correct_shape(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (duplicate)']);

        $tool = app(MergeDuplicateEntities::class);
        $parts = $tool->buildParts([
            'survivor_id' => $survivor->entity_id,
            'loser_id' => $loser->entity_id,
        ]);

        $this->assertCount(1, $parts);

        $part = $parts[0];
        $this->assertSame('merge', $part['key']);
        $this->assertSame('merge_duplicate_entities', $part['tool']);
        $this->assertSame($survivor->entity_id, $part['payload']['survivor_id']);
        $this->assertSame($loser->entity_id, $part['payload']['loser_id']);
        $this->assertArrayHasKey('summary', $part['human_diff']);
        $this->assertStringContainsString($survivor->name, $part['human_diff']['summary']);
        $this->assertStringContainsString($loser->name, $part['human_diff']['summary']);
    }

    // ── 2. applyPart calls MergeEntitiesAction and returns survivor id ────────

    public function test_apply_part_calls_action_and_returns_survivor_id(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        $this->mock(MergeEntitiesAction::class, function (MockInterface $mock) use ($survivor, $loser): void {
            $mock->shouldReceive('__invoke')
                ->once()
                ->with($survivor->entity_id, $loser->entity_id)
                ->andReturn($survivor);
        });

        $tool = app(MergeDuplicateEntities::class);
        $result = $tool->applyPart([
            'survivor_id' => $survivor->entity_id,
            'loser_id' => $loser->entity_id,
        ], ['user_id' => 'u1']);

        $this->assertArrayHasKey('result_id', $result);
        $this->assertSame($survivor->entity_id, $result['result_id']);
        $this->assertArrayHasKey('summary', $result);
    }

    // ── 3. applyPart actually merges (integration) ───────────────────────────

    public function test_apply_part_actually_merges_entities(): void
    {
        $survivor = Entity::factory()->create(['name' => 'Italy']);
        $loser = Entity::factory()->create(['name' => 'Italy (dup)']);

        $tool = app(MergeDuplicateEntities::class);
        $result = $tool->applyPart([
            'survivor_id' => $survivor->entity_id,
            'loser_id' => $loser->entity_id,
        ], ['user_id' => 'u1']);

        $this->assertSame($survivor->entity_id, $result['result_id']);
        $this->assertDatabaseHas('entities', ['entity_id' => $survivor->entity_id]);
        $this->assertDatabaseMissing('entities', ['entity_id' => $loser->entity_id]);
    }

    // ── 4. Tool name constant ─────────────────────────────────────────────────

    public function test_tool_name_is_merge_duplicate_entities(): void
    {
        $this->assertSame('merge_duplicate_entities', MergeDuplicateEntities::name());
    }
}
