<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesFeatureShapeTest extends TestCase
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

    public function test_feature_properties_have_exact_trimmed_shape(): void
    {
        $entity = Entity::factory()->verified()->create([
            'impact_score' => 50,
            'attributes' => ['entity_color' => '#abcdef'],
        ]);
        $this->setGeometryPeriod($entity, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();
        $props = $response->json('features.0.properties');

        $this->assertEqualsCanonicalizing(
            ['id', 'name', 'entity_type', 'entity_group', 'impact_score', 'start_year', 'end_year', 'entity_color'],
            array_keys($props),
        );
        $this->assertSame('#abcdef', $props['entity_color']);
    }
}
