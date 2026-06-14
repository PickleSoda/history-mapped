<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesCacheTest extends TestCase
{
    use RefreshDatabase;

    private function seedPeriod(): void
    {
        $entity = Entity::factory()->verified()->create();

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id],
        );
    }

    /** @return array<string, mixed> */
    private function mapQuery(): array
    {
        return [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ];
    }

    public function test_map_response_carries_etag_and_cache_control(): void
    {
        $this->seedPeriod();

        $response = $this->get(route('api.v1.entities.map', $this->mapQuery()));

        $response->assertOk();
        $this->assertNotEmpty($response->headers->get('ETag'));
        $this->assertNotEmpty($response->headers->get('Cache-Control'));
    }

    public function test_repeat_request_with_if_none_match_returns_304(): void
    {
        $this->seedPeriod();

        $first = $this->get(route('api.v1.entities.map', $this->mapQuery()));
        $first->assertOk();
        $etag = $first->headers->get('ETag');
        $this->assertNotEmpty($etag);

        $second = $this->get(
            route('api.v1.entities.map', $this->mapQuery()),
            ['If-None-Match' => $etag],
        );

        $second->assertStatus(304);
    }

    public function test_year_endpoint_carries_etag(): void
    {
        $this->seedPeriod();

        $response = $this->get(route('api.v1.entities.map.year', ['year' => 1000]));

        $response->assertOk();
        $this->assertNotEmpty($response->headers->get('ETag'));
    }
}
