<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesTemporalRangeTest extends TestCase
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

    private function bbox(): array
    {
        return [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
        ];
    }

    public function test_temporal_range_replaces_the_year_default(): void
    {
        $entity = Entity::factory()->verified()->create();
        // Exists 1500–1600 only — NOT at the old silent default year 1000.
        $this->setGeometryPeriod($entity, 1500, 1600);

        $response = $this->getJson(route('api.v1.entities.map', [
            ...$this->bbox(),
            'temporal_start' => 1500,
            'temporal_end' => 1600,
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($entity->entity_id, $ids);
    }

    public function test_requires_year_or_range(): void
    {
        $response = $this->getJson(route('api.v1.entities.map', $this->bbox()));
        $response->assertStatus(422);
    }
}
