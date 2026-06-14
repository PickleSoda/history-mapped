<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesConfidenceTest extends TestCase
{
    use RefreshDatabase;

    private function setGeometryPeriod(Entity $entity, int $startYear, int $endYear): void
    {
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', ?, ?,
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id, $startYear, $endYear],
        );
    }

    public function test_min_confidence_returns_more_confident_and_excludes_less(): void
    {
        $high = Entity::factory()->verified()->create(['confidence' => 'high']);
        $low = Entity::factory()->verified()->create(['confidence' => 'low']);
        $this->setGeometryPeriod($high, 900, 1100);
        $this->setGeometryPeriod($low, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
            'min_confidence' => 'medium',
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();

        $this->assertContains($high->entity_id, $ids, 'high-confidence entity should be included by min_confidence=medium');
        $this->assertNotContains($low->entity_id, $ids, 'low-confidence entity should be excluded by min_confidence=medium');
    }
}
