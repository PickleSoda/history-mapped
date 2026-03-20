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
        DB::table('entities')
            ->where('entity_id', $entity->entity_id)
            ->update(['geom' => DB::raw("ST_SetSRID(ST_Point({$lng}, {$lat}), 4326)")]);
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
}
