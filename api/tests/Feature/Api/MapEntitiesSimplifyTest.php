<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesSimplifyTest extends TestCase
{
    use RefreshDatabase;

    private function setDensePeriod(Entity $entity): void
    {
        // A many-vertex polygon (edges segmentized) so simplification can reduce it.
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_Segmentize(ST_GeomFromText('POLYGON((5 35, 25 35, 25 45, 5 45, 5 35))'), 0.2), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id],
        );
    }

    private function ringVertexCount(array $response): int
    {
        $feature = $response['features'][0] ?? null;
        $this->assertNotNull($feature, 'expected a feature');

        return count($feature['geometry']['coordinates'][0]);
    }

    public function test_low_zoom_returns_fewer_vertices_than_high_zoom(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setDensePeriod($entity);

        $bbox = [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
            'min_impact' => 0, // isolate simplification from the zoom impact threshold
        ];

        $low = $this->getJson(route('api.v1.entities.map', [...$bbox, 'zoom_level' => 2]))->json();
        $high = $this->getJson(route('api.v1.entities.map', [...$bbox, 'zoom_level' => 14]))->json();

        $this->assertLessThan(
            $this->ringVertexCount($high),
            $this->ringVertexCount($low),
            'low-zoom geometry should be simplified to fewer vertices',
        );
    }
}
