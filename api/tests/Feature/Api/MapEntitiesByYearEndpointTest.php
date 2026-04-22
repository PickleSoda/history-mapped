<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesByYearEndpointTest extends TestCase
{
    use RefreshDatabase;

    private function setGeometryPeriod(
        Entity $entity,
        int $startYear,
        int $endYear,
        ?string $polygonWkt = null,
    ): void
    {
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

    public function test_year_only_endpoint_requires_year_but_not_bbox(): void
    {
        $this->getJson(route('api.v1.entities.map.year'))
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['year']);

        $this->getJson(route('api.v1.entities.map.year', ['year' => 1000]))
            ->assertOk();
    }

    public function test_year_only_endpoint_returns_entities_existing_in_given_year(): void
    {
        $inYear = Entity::factory()->verified()->create(['name' => 'In Year']);
        $this->setGeometryPeriod($inYear, 900, 1100);

        $outOfYear = Entity::factory()->verified()->create(['name' => 'Out Of Year']);
        $this->setGeometryPeriod(
            $outOfYear,
            1200,
            1300,
            'POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))',
        );

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');

        $this->assertContains($inYear->entity_id, $ids);
        $this->assertNotContains($outOfYear->entity_id, $ids);
    }

    public function test_year_only_endpoint_supports_min_impact_filter(): void
    {
        $high = Entity::factory()->verified()->create(['impact_score' => 92]);
        $this->setGeometryPeriod($high, 900, 1100);

        $low = Entity::factory()->verified()->create(['impact_score' => 40]);
        $this->setGeometryPeriod(
            $low,
            900,
            1100,
            'POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))',
        );

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
            'min_impact' => 90,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');

        $this->assertContains($high->entity_id, $ids);
        $this->assertNotContains($low->entity_id, $ids);
    }
}
