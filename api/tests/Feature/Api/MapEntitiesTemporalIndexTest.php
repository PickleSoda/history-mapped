<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesTemporalIndexTest extends TestCase
{
    use RefreshDatabase;

    private function setGeometryPeriod(Entity $entity, int $startYear, ?int $endYear): void
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

    private function bbox(array $extra): array
    {
        return array_merge([
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
        ], $extra);
    }

    public function test_open_ended_period_matches_year_after_start(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 1000, null); // ongoing

        $response = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1500])));
        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($entity->entity_id, $ids);
    }

    public function test_end_year_is_inclusive(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 900, 1100);

        $atEnd = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1100])));
        $this->assertContains($entity->entity_id, collect($atEnd->json('features'))->pluck('id')->all());

        $afterEnd = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1101])));
        $this->assertNotContains($entity->entity_id, collect($afterEnd->json('features'))->pluck('id')->all());
    }

    public function test_range_overlap(): void
    {
        $inRange = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($inRange, 1500, 1600);

        $outRange = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($outRange, 1000, 1100);

        $response = $this->getJson(route('api.v1.entities.map', $this->bbox([
            'temporal_start' => 1550,
            'temporal_end' => 1700,
        ])));
        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($inRange->entity_id, $ids);
        $this->assertNotContains($outRange->entity_id, $ids);
    }
}
