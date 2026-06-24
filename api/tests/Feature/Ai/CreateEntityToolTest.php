<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\CreateEntity;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class CreateEntityToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_then_apply_creates_a_located_entity_with_agent_provenance(): void
    {
        $wikidataPayload = [
            'entities' => [
                'Q28567' => [
                    'labels' => ['en' => ['value' => 'Maya civilization']],
                    'claims' => [
                        'P31' => [
                            ['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q11514315']]]],
                        ],
                    ],
                ],
            ],
        ];
        Http::fake(['*' => Http::response($wikidataPayload)]);

        $tool = app(CreateEntity::class);
        $parts = $tool->buildParts([
            'name' => 'Maya civilization', 'entity_type' => 'political_entity',
            'wikidata_id' => 'Q28567', 'lon' => -89.6, 'lat' => 17.2,
        ]);
        $this->assertCount(1, $parts);
        $this->assertSame('create_entity', $parts[0]['tool']);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);
        $entity = Entity::findOrFail($result['result_id']);

        $this->assertSame('Maya civilization', $entity->name);
        $this->assertSame('political_entity', $entity->entity_type->value);
        $this->assertSame('agent:u1', $entity->created_by);
        $this->assertNotNull($entity->primaryLocation);
    }
}
