<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\VerificationStatus;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesThresholdTest extends TestCase
{
    use RefreshDatabase;

    /**
     * Insert a geometry into an entity so that it is returned by the map endpoint.
     */
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

    public function test_map_endpoint_requires_bbox(): void
    {
        $this->getJson(route('api.v1.entities.map'))
            ->assertUnprocessable();
    }

    public function test_zoom_level_1_filters_out_low_impact_entities(): void
    {
        // impact 85 — should appear at zoom 1 (threshold 80)
        $high = Entity::factory()->verified()->create(['impact_score' => 85]);
        $this->setGeom($high);

        // impact 50 — should not appear at zoom 1 (threshold 80)
        $low = Entity::factory()->verified()->create(['impact_score' => 50]);
        $this->setGeom($low, 12.6, 42.0);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'zoom_level' => 1,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($high->entity_id, $ids);
        $this->assertNotContains($low->entity_id, $ids);
    }

    public function test_zoom_level_12_applies_no_threshold(): void
    {
        // impact 5 — should appear at zoom 12 (no threshold)
        $low = Entity::factory()->verified()->create(['impact_score' => 5]);
        $this->setGeom($low);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'zoom_level' => 12,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($low->entity_id, $ids);
    }

    public function test_explicit_min_impact_overrides_zoom_level(): void
    {
        // zoom 1 would imply threshold 80, but min_impact=30 overrides it
        $mid = Entity::factory()->verified()->create(['impact_score' => 50]);
        $this->setGeom($mid);

        $low = Entity::factory()->verified()->create(['impact_score' => 10]);
        $this->setGeom($low, 12.6, 42.0);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'zoom_level' => 1,
            'min_impact' => 30,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($mid->entity_id, $ids);
        $this->assertNotContains($low->entity_id, $ids);
    }

    public function test_without_zoom_or_min_impact_no_threshold_is_applied(): void
    {
        $low = Entity::factory()->verified()->create(['impact_score' => 1]);
        $this->setGeom($low);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');
        $this->assertContains($low->entity_id, $ids);
    }

    public function test_map_can_include_territories_from_geometry_periods_with_threshold_filtering(): void
    {
        $high = Entity::factory()->verified()->create(['impact_score' => 90]);
        $low = Entity::factory()->verified()->create(['impact_score' => 20]);

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES
            (
                gen_random_uuid(), ?, 'territory', -100, -50,
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            ),
            (
                gen_random_uuid(), ?, 'territory', -100, -50,
                ST_SetSRID(ST_GeomFromText('POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$high->entity_id, $low->entity_id],
        );

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'zoom_level' => 1,
            'include_territories' => true,
        ]));

        $response->assertOk();

        $territories = $response->json('territories');
        $territoryEntityIds = array_column($territories, 'entity_id');

        $this->assertContains($high->entity_id, $territoryEntityIds);
        $this->assertNotContains($low->entity_id, $territoryEntityIds);
    }
}
