<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesBboxTest extends TestCase
{
    use RefreshDatabase;

    private function insertPoint(Entity $entity, float $lng, float $lat): void
    {
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_Point(?, ?), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id, $lng, $lat],
        );
    }

    public function test_feature_excluded_when_coalesced_geometry_off_viewport(): void
    {
        $entity = Entity::factory()->verified()->create();
        // Territory (preferred by COALESCE) is far outside the bbox; the point is inside.
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_Point(10, 40), 4326),
                ST_SetSRID(ST_GeomFromText('POLYGON((100 40, 101 40, 101 41, 100 41, 100 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id],
        );

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertNotContains($entity->entity_id, $ids);
    }

    public function test_antimeridian_viewport_returns_both_sides(): void
    {
        $east = Entity::factory()->verified()->create();
        $west = Entity::factory()->verified()->create();
        $this->insertPoint($east, 170, 40);
        $this->insertPoint($west, -170, 40);

        // Viewport crosses the dateline: min_lng (160) > max_lng (-160).
        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 160,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => -160,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($east->entity_id, $ids);
        $this->assertContains($west->entity_id, $ids);
    }
}
