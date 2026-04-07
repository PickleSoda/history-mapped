<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_index_returns_snapshots_for_entity(): void
    {
        $entity = Entity::factory()->create();
        $otherEntity = Entity::factory()->create();

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -50,
            'end_year' => -40,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'description' => 'Primary territory period',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[10.0, 40.0], [11.0, 40.0], [11.0, 41.0], [10.0, 41.0], [10.0, 40.0]]],
            ],
        ]);

        GeometryPeriod::query()->create([
            'entity_id' => $otherEntity->entity_id,
            'period_type' => 'territory',
            'start_year' => -20,
            'end_year' => -10,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[20.0, 40.0], [21.0, 40.0], [21.0, 41.0], [20.0, 41.0], [20.0, 40.0]]],
            ],
        ]);

        $this->getJson("/api/v1/entities/{$entity->entity_id}/geometry-snapshots")
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.entity_id', $entity->entity_id)
            ->assertJsonPath('data.0.year_start', -50)
            ->assertJsonPath('data.0.year_end', -40)
            ->assertJsonPath('data.0.source_table', 'geometry_periods');
    }

    public function test_at_year_returns_matching_snapshot(): void
    {
        $entity = Entity::factory()->create();

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -80,
            'end_year' => -60,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
            ],
        ]);

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -59,
            'end_year' => -20,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'description' => 'Expansion era territory',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[12.0, 12.0], [13.0, 12.0], [13.0, 13.0], [12.0, 13.0], [12.0, 12.0]]],
            ],
        ]);

        $matchingPeriodId = (string) GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('start_year', -59)
            ->where('end_year', -20)
            ->value('geometry_period_id');

        $this->getJson("/api/v1/entities/{$entity->entity_id}/geometry-snapshots/at-year/-30")
            ->assertOk()
            ->assertJsonPath('data.snapshot_id', $matchingPeriodId)
            ->assertJsonPath('data.year_start', -59)
            ->assertJsonPath('data.year_end', -20)
            ->assertJsonPath('data.source_table', 'geometry_periods');
    }
}
