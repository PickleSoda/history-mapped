<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\SetEntityLocation;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SetEntityLocationToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_parts_returns_one_location_part(): void
    {
        $entity = Entity::factory()->create(['name' => 'Roman Empire']);

        $tool = app(SetEntityLocation::class);
        $parts = $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'lon' => 12.5,
            'lat' => 41.9,
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('location', $parts[0]['key']);
        $this->assertSame('set_entity_location', $parts[0]['tool']);
        $this->assertSame([12.5, 41.9], $parts[0]['human_diff']['to']);
    }

    public function test_apply_part_sets_geom_with_human_assigned_method(): void
    {
        $entity = Entity::factory()->create(['name' => 'Roman Empire']);

        $tool = app(SetEntityLocation::class);
        $payload = [
            'entity_id' => $entity->entity_id,
            'lon' => 12.5,
            'lat' => 41.9,
        ];

        $result = $tool->applyPart($payload, ['user_id' => 'u1']);

        $this->assertSame($entity->entity_id, $result['result_id']);
        $this->assertSame('Location updated', $result['summary']);

        $entity->refresh();
        $location = $entity->primaryLocation;
        $this->assertNotNull($location);
        $this->assertSame(LocationResolutionMethod::HumanAssigned, $location->location_method);

        // Coordinates stored in GeoJSON form
        $coords = $location->geom['coordinates'] ?? ($location->geom->coordinates ?? null);
        $this->assertEqualsWithDelta(12.5, $coords[0], 0.001);
        $this->assertEqualsWithDelta(41.9, $coords[1], 0.001);
    }
}
