<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EntityDetailGeometrySnapshotsCountTest extends TestCase
{
    use RefreshDatabase;

    public function test_entity_detail_includes_geometry_snapshots_count(): void
    {
        $entity = Entity::factory()->create();

        GeometrySnapshot::factory()->forEntity($entity)->forYears(-27, 14)->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(14, 117)->create();

        $response = $this->getJson(route('api.v1.entities.show', $entity));

        $response->assertOk()
            ->assertJsonPath('data.geometry_snapshots_count', 2);
    }
}
