<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\ToolArgumentException;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use App\Models\EntityLocation;
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

    public function test_moving_the_point_keeps_the_territory(): void
    {
        $entity = Entity::factory()->create(['name' => 'Roman Empire']);
        $territory = ['type' => 'Polygon', 'coordinates' => [[[10, 40], [14, 40], [14, 44], [10, 44], [10, 40]]]];
        EntityLocation::create([
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [12, 42]],
            'territory_geom' => $territory,
            'location_name' => 'Latium',
            'location_method' => 'wikidata',
        ]);

        app(SetEntityLocation::class)->applyPart([
            'entity_id' => $entity->entity_id, 'lon' => 12.4964, 'lat' => 41.9028,
            'location_name' => 'Rome', 'location_confidence' => 'high',
        ], ['user_id' => 'u1']);

        $location = $entity->refresh()->primaryLocation;
        $this->assertEqualsWithDelta(12.4964, $location->geom['coordinates'][0], 0.0001);
        $this->assertSame('Polygon', $location->territory_geom['type'] ?? null, 'the territory polygon survives');
        $this->assertSame('Rome', $location->location_name);
        $this->assertSame('high', $location->location_confidence?->value);
    }

    public function test_rejects_out_of_range_coordinates(): void
    {
        $entity = Entity::factory()->create();

        $this->expectException(ToolArgumentException::class);
        app(SetEntityLocation::class)->buildParts(['entity_id' => $entity->entity_id, 'lon' => 41.9, 'lat' => 112.5]);
    }
}
