<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\CreateRelationship;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateRelationshipToolTest extends TestCase
{
    use RefreshDatabase;

    // -------------------------------------------------------------------------
    // Test 1 — existing target: one part, no depends_on
    // -------------------------------------------------------------------------

    public function test_build_parts_returns_one_part_when_target_entity_id_is_provided(): void
    {
        $source = Entity::factory()->create(['name' => 'Roman Empire']);
        $target = Entity::factory()->create(['name' => 'Italy']);

        $tool = app(CreateRelationship::class);
        $parts = $tool->buildParts([
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'contains',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('relationship', $parts[0]['key']);
        $this->assertSame('create_relationship', $parts[0]['tool']);
        $this->assertNull($parts[0]['depends_on'] ?? null);
        $this->assertSame($target->entity_id, $parts[0]['payload']['target_entity_id']);
    }

    public function test_apply_part_creates_relationship_between_existing_entities(): void
    {
        $source = Entity::factory()->create(['name' => 'Roman Empire']);
        $target = Entity::factory()->create(['name' => 'Italy']);

        $tool = app(CreateRelationship::class);
        $parts = $tool->buildParts([
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'contains',
        ]);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);

        $this->assertArrayHasKey('result_id', $result);
        $this->assertSame('Relationship created', $result['summary']);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'contains',
            'created_by' => 'agent:u1',
        ]);
    }

    // -------------------------------------------------------------------------
    // Test 2 — missing target (new_target): two parts, second depends on first
    // -------------------------------------------------------------------------

    public function test_build_parts_returns_two_parts_when_new_target_is_provided(): void
    {
        $source = Entity::factory()->create(['name' => 'Roman Empire']);

        $tool = app(CreateRelationship::class);
        $parts = $tool->buildParts([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => 'contains',
            'new_target' => [
                'name' => 'Gaul',
                'entity_type' => 'political_entity',
            ],
        ]);

        $this->assertCount(2, $parts);

        // First part: entity creation (delegated to create_entity tool)
        $this->assertSame('target', $parts[0]['key']);
        $this->assertSame('create_entity', $parts[0]['tool']);
        $this->assertArrayNotHasKey('depends_on', $parts[0]);

        // Second part: relationship creation, depends on target
        $this->assertSame('relationship', $parts[1]['key']);
        $this->assertSame('create_relationship', $parts[1]['tool']);
        $this->assertSame('target', $parts[1]['depends_on']);
        $this->assertNull($parts[1]['payload']['target_entity_id']);
    }

    public function test_apply_part_uses_resolved_depends_for_target_id_when_new_target(): void
    {
        $source = Entity::factory()->create(['name' => 'Roman Empire']);
        $targetEntity = Entity::factory()->create(['name' => 'Gaul']);

        $tool = app(CreateRelationship::class);

        // Simulate: the 'target' part was already applied and produced $targetEntity->entity_id
        $payload = [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => null, // not yet resolved — comes from depends
            'relationship_type' => 'contains',
            'start_year' => null,
            'end_year' => null,
        ];

        $result = $tool->applyPart($payload, [
            'depends' => $targetEntity->entity_id,
            'user_id' => 'u1',
        ]);

        $this->assertArrayHasKey('result_id', $result);
        $this->assertSame('Relationship created', $result['summary']);

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $targetEntity->entity_id,
            'relationship_type' => 'contains',
            'created_by' => 'agent:u1',
        ]);
    }
}
