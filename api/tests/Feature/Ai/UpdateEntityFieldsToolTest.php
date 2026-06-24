<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\UpdateEntityFields;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class UpdateEntityFieldsToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_parts_diffs_only_provided_fields(): void
    {
        $entity = Entity::factory()->create([
            'name' => 'Byzantine Empire',
            'summary' => 'Old summary',
        ]);

        $tool = app(UpdateEntityFields::class);
        $parts = $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'summary' => 'New summary',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('update_entity_fields', $parts[0]['tool']);
        $this->assertArrayHasKey('summary', $parts[0]['human_diff']['diff']);
        $this->assertArrayNotHasKey('name', $parts[0]['human_diff']['diff']);
        $this->assertSame('Old summary', $parts[0]['human_diff']['diff']['summary']['from']);
        $this->assertSame('New summary', $parts[0]['human_diff']['diff']['summary']['to']);
    }

    public function test_apply_part_updates_summary_and_preserves_other_fields(): void
    {
        $entity = Entity::factory()->create([
            'name' => 'Byzantine Empire',
            'summary' => 'Old summary',
            'significance' => 'Very significant',
        ]);

        $tool = app(UpdateEntityFields::class);
        $result = $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'summary' => 'Updated summary',
        ], ['user_id' => 'u1']);

        $this->assertSame($entity->entity_id, $result['result_id']);
        $this->assertSame('Fields updated', $result['summary']);

        $entity->refresh();
        $this->assertSame('Updated summary', $entity->summary);
        // Other fields preserved
        $this->assertSame('Byzantine Empire', $entity->name);
        $this->assertSame('Very significant', $entity->significance);
    }

    public function test_apply_part_updates_name(): void
    {
        $entity = Entity::factory()->create(['name' => 'Old Name']);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'name' => 'New Name',
        ], ['user_id' => 'u1']);

        $entity->refresh();
        $this->assertSame('New Name', $entity->name);
    }
}
