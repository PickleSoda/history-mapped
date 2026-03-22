<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_index_returns_snapshots_for_entity(): void
    {
        $entity = Entity::factory()->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(-27, 14)->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(14, 117)->create();

        $response = $this->getJson(route('api.v1.entities.geometry-snapshots.index', $entity));

        $response->assertOk();
        $this->assertCount(2, $response->json('data'));
    }

    public function test_at_year_returns_matching_snapshot(): void
    {
        $entity = Entity::factory()->create();

        GeometrySnapshot::factory()->forEntity($entity)->forYears(0, 100)->create([
            'display_priority' => 1,
        ]);

        $expected = GeometrySnapshot::factory()->forEntity($entity)->forYears(50, 80)->create([
            'display_priority' => 9,
            'label' => 'Preferred overlap',
        ]);

        $response = $this->getJson(route('api.v1.entities.geometry-snapshots.at-year', [
            'entity' => $entity,
            'year' => 60,
        ]));

        $response->assertOk()
            ->assertJsonPath('data.snapshot_id', $expected->snapshot_id)
            ->assertJsonPath('data.label', 'Preferred overlap');
    }
}
