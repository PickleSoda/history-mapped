<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::factory()->create();
    }

    public function test_index_returns_snapshots_for_entity(): void
    {
        $entity = Entity::factory()->create();
        $other = Entity::factory()->create();

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -50,
            'end_year' => -20,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0], [1.0, 1.0]]],
            ],
        ]);

        GeometryPeriod::query()->create([
            'entity_id' => $other->entity_id,
            'period_type' => 'territory',
            'start_year' => -10,
            'end_year' => -5,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[3.0, 3.0], [4.0, 3.0], [4.0, 4.0], [3.0, 4.0], [3.0, 3.0]]],
            ],
        ]);

        $this->actingAs($this->user)
            ->getJson(route('entities.geometry-snapshots.index', $entity))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.entity_id', $entity->entity_id)
            ->assertJsonPath('data.0.source_table', 'geometry_periods');
    }

    public function test_store_rejects_manual_presence_entries(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-snapshots.store', $entity), [
                'period_type' => 'presence',
                'start_year' => -44,
                'end_year' => -44,
                'provenance_mode' => 'manual',
                'geom' => [
                    'type' => 'Point',
                    'coordinates' => [12.5, 41.9],
                ],
            ])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['period_type']);
    }

    public function test_store_creates_territory_geometry_period(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-snapshots.store', $entity), [
                'period_type' => 'territory',
                'start_year' => -80,
                'end_year' => -20,
                'provenance_mode' => 'manual',
                'description' => 'Administrative test snapshot',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
                ],
            ])
            ->assertCreated()
            ->assertJsonPath('data.entity_id', $entity->entity_id)
            ->assertJsonPath('data.period_type', 'territory');

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -80,
            'end_year' => -20,
            'provenance_mode' => 'manual',
            'description' => 'Administrative test snapshot',
        ]);
    }
}
