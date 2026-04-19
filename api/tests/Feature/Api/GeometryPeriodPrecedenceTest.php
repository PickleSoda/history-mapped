<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class GeometryPeriodPrecedenceTest extends TestCase
{
    use RefreshDatabase;

    private function setGeom(Entity $entity, float $lng = 12.5, float $lat = 41.9): void
    {
        DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_SetSRID(ST_Point(?, ?), 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true,
                NOW(),
                NOW()
            )",
            [$entity->entity_id, $lng, $lat],
        );
    }

    public function test_geometry_period_takes_precedence_over_base_geometry(): void
    {
        $entity = Entity::factory()
            ->verified()
            ->withTemporalRange('900', '1100')
            ->create();

        $this->setGeom($entity, 10.0, 40.0);

        $period = GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => 950,
            'end_year' => 1050,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [11.0, 41.0],
            ],
            'provenance_mode' => 'manual',
            'created_by' => 'test',
        ]);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();

        $feature = collect($response->json('features'))
            ->firstWhere('id', $entity->entity_id);

        $this->assertNotNull($feature);
        $this->assertEquals([11.0, 41.0], $feature['geometry']['coordinates'] ?? null);
    }

    public function test_does_not_fallback_to_base_geometry_when_no_period_matches(): void
    {
        $entity = Entity::factory()
            ->verified()
            ->withTemporalRange('900', '1100')
            ->create();

        $this->setGeom($entity, 10.0, 40.0);

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => 1100,
            'end_year' => 1200,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [11.0, 41.0],
            ],
            'provenance_mode' => 'manual',
            'created_by' => 'test',
        ]);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();

        $feature = collect($response->json('features'))
            ->firstWhere('id', $entity->entity_id);

        $this->assertNull($feature);
    }
}
