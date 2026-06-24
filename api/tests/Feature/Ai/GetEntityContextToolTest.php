<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\GetEntityContext;
use App\Models\Entity;
use App\Models\EntityLocation;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Ai\Tools\Request;
use LogicException;
use Tests\TestCase;

class GetEntityContextToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_handle_returns_json_with_entity_name_and_type(): void
    {
        $entity = Entity::factory()->create([
            'name' => 'Ottoman Empire',
            'summary' => 'A long-lived empire',
        ]);

        $tool = app(GetEntityContext::class)->forEntity($entity);
        $json = $tool->handle(new Request([]));

        $data = json_decode($json, true);
        $this->assertSame('Ottoman Empire', $data['name']);
        $this->assertSame($entity->entity_id, $data['entity_id']);
        $this->assertArrayHasKey('entity_type', $data);
        $this->assertArrayHasKey('relationships', $data);
    }

    public function test_handle_includes_location_when_present(): void
    {
        $entity = Entity::factory()->create(['name' => 'Constantinople']);
        EntityLocation::create([
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [28.97, 41.01]],
            'location_method' => 'wikidata',
        ]);

        $tool = app(GetEntityContext::class)->forEntity($entity);
        $json = $tool->handle(new Request([]));

        $data = json_decode($json, true);
        $this->assertNotNull($data['location']);
        $this->assertEqualsWithDelta(28.97, $data['location']['lon'], 0.001);
        $this->assertEqualsWithDelta(41.01, $data['location']['lat'], 0.001);
    }

    public function test_build_parts_throws_logic_exception(): void
    {
        $entity = Entity::factory()->create();
        $tool = app(GetEntityContext::class)->forEntity($entity);

        $this->expectException(LogicException::class);
        $tool->buildParts([]);
    }

    public function test_apply_part_throws_logic_exception(): void
    {
        $entity = Entity::factory()->create();
        $tool = app(GetEntityContext::class)->forEntity($entity);

        $this->expectException(LogicException::class);
        $tool->applyPart([], []);
    }
}
