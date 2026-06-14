<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesYearFilteringTest extends TestCase
{
    use RefreshDatabase;

    private function setGeometryPeriod(
        Entity $entity,
        int $startYear,
        int $endYear,
        ?string $polygonWkt = null,
    ): void {
        $polygon = $polygonWkt ?? 'POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))';

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', ?, ?,
                ST_SetSRID(ST_GeomFromText(?), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id, $startYear, $endYear, $polygon],
        );
    }

    public function test_map_endpoint_accepts_year_parameter(): void
    {
        $entity = Entity::factory()
            ->verified()
            ->create();

        $this->setGeometryPeriod($entity, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();
        $response->assertJsonStructure([
            'type',
            'features' => [
                '*' => [
                    'type',
                    'id',
                    'geometry',
                    'properties',
                ],
            ],
        ]);
    }

    public function test_map_endpoint_validates_year_as_integer(): void
    {
        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 'invalid',
        ]));

        $response->assertUnprocessable();
        $response->assertJsonValidationErrors(['year']);
    }

    public function test_explicit_year_filters_periods(): void
    {
        $inYear = Entity::factory()
            ->verified()
            ->create(['name' => 'In Year']);
        $this->setGeometryPeriod($inYear, 900, 1100);

        $outOfYear = Entity::factory()
            ->verified()
            ->create(['name' => 'Out Of Year']);
        $this->setGeometryPeriod(
            $outOfYear,
            1200,
            1300,
            'POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))',
        );

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();

        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($inYear->entity_id, $ids);
        $this->assertNotContains($outOfYear->entity_id, $ids);
    }

    public function test_year_filter_includes_entity_when_geometry_period_covers_year(): void
    {
        $entity = Entity::factory()
            ->verified()
            ->create(['name' => 'Geometry Period Coverage']);
        $this->setGeometryPeriod($entity, 980, 1040);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();

        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($entity->entity_id, $ids);
    }
}
