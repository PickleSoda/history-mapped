<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\UpdateEntityFields;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
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

    public function test_apply_part_preserves_end_date_when_only_start_year_supplied(): void
    {
        $entity = Entity::factory()->create();
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => '-100',
            'end_date' => '50',
        ]);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'start_year' => -90,
        ], ['user_id' => 'u1']);

        $entity->load('primaryTemporalRange');
        $temporal = $entity->primaryTemporalRange;
        $this->assertNotNull($temporal, 'Primary temporal range should exist');
        $this->assertSame('-90', $temporal->start_date, 'start_date should be updated to -90');
        $this->assertSame('50', $temporal->end_date, 'end_date should be preserved at 50');
    }

    public function test_apply_part_preserves_start_date_when_only_end_year_supplied(): void
    {
        $entity = Entity::factory()->create();
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => '-100',
            'end_date' => '50',
        ]);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'end_year' => 75,
        ], ['user_id' => 'u1']);

        $entity->load('primaryTemporalRange');
        $temporal = $entity->primaryTemporalRange;
        $this->assertNotNull($temporal, 'Primary temporal range should exist');
        $this->assertSame('-100', $temporal->start_date, 'start_date should be preserved at -100');
        $this->assertSame('75', $temporal->end_date, 'end_date should be updated to 75');
    }
}
