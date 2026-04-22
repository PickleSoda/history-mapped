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
     * Insert a geometry period so that it is returned by the map endpoint.
     */
    private function setGeometryPeriod(
        Entity $entity,
        int $startYear,
        int $endYear,
        string $periodType = 'territory',
        ?string $polygonWkt = null,
    ): void
    {
        $polygon = $polygonWkt ?? 'POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))';

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, ?, ?, ?,
                ST_SetSRID(ST_GeomFromText(?), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id, $periodType, $startYear, $endYear, $polygon],
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
        $this->setGeometryPeriod($high, 900, 1100);

        // impact 50 — should not appear at zoom 1 (threshold 80)
        $low = Entity::factory()->verified()->create(['impact_score' => 50]);
        $this->setGeometryPeriod(
            $low,
            900,
            1100,
            'territory',
            'POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))',
        );

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
        $this->setGeometryPeriod($low, 900, 1100);

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
        $this->setGeometryPeriod($mid, 900, 1100);

        $low = Entity::factory()->verified()->create(['impact_score' => 10]);
        $this->setGeometryPeriod(
            $low,
            900,
            1100,
            'territory',
            'POLYGON((12 40, 13 40, 13 41, 12 41, 12 40))',
        );

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
        $this->setGeometryPeriod($low, 900, 1100);

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

    public function test_map_response_does_not_duplicate_features_under_entities_key(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
        ]));

        $response->assertOk();
        $response->assertJsonMissingPath('entities');
    }

    public function test_global_bbox_respects_requested_limit_without_hard_clamp(): void
    {
        for ($i = 0; $i < 90; $i++) {
            $entity = Entity::factory()->verified()->create();
            $baseLng = -170 + ($i * 0.5);
            $baseLat = -60 + ($i * 0.3);

            $this->setGeometryPeriod(
                $entity,
                1400,
                1600,
                'territory',
                sprintf(
                    'POLYGON((%1$.2f %2$.2f, %3$.2f %2$.2f, %3$.2f %4$.2f, %1$.2f %4$.2f, %1$.2f %2$.2f))',
                    $baseLng,
                    $baseLat,
                    $baseLng + 0.2,
                    $baseLat + 0.2,
                ),
            );
        }

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => -180,
            'bbox_min_lat' => -85,
            'bbox_max_lng' => 180,
            'bbox_max_lat' => 85,
            'year' => 1500,
            'limit' => 500,
        ]));

        $response->assertOk();
        $this->assertCount(90, $response->json('features'));
    }

    public function test_map_returns_border_period_type_in_feature_properties(): void
    {
        $entity = Entity::factory()->verified()->create(['impact_score' => 90]);
        $this->setGeometryPeriod($entity, -100, -50, 'territory');

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => -80,
        ]));

        $response->assertOk();

        $feature = collect($response->json('features'))
            ->firstWhere('id', $entity->entity_id);

        $this->assertNotNull($feature);
        $this->assertSame('territory', $feature['properties']['period_type'] ?? null);
        $response->assertJsonMissingPath('territories');
    }

    public function test_map_bbox_matches_geometry_period_territory_only(): void
    {
        $territoryEntity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($territoryEntity, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 9,
            'bbox_min_lat' => 39,
            'bbox_max_lng' => 12,
            'bbox_max_lat' => 42,
            'year' => 1000,
        ]));

        $response->assertOk();

        $feature = collect($response->json('features'))
            ->firstWhere('id', $territoryEntity->entity_id);

        $this->assertNotNull($feature);
        $this->assertSame('Polygon', $feature['geometry']['type'] ?? null);
    }

    public function test_map_includes_ohm_draft_entities_from_pipeline_imports(): void
    {
        $imported = Entity::factory()->create([
            'verification_status' => VerificationStatus::OhmDraft->value,
            'impact_score' => 42,
        ]);
        $this->setGeometryPeriod(
            $imported,
            900,
            1100,
            'territory',
            'POLYGON((15 45, 16 45, 16 46, 15 46, 15 45))',
        );

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 10,
            'bbox_min_lat' => 40,
            'bbox_max_lng' => 20,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]));

        $response->assertOk();
        $ids = array_column($response->json('features'), 'id');

        $this->assertContains($imported->entity_id, $ids);
    }

    public function test_map_bbox_matches_entities_with_geometry_period_territory_only(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 9,
            'bbox_min_lat' => 39,
            'bbox_max_lng' => 12,
            'bbox_max_lat' => 42,
            'year' => 1000,
        ]));

        $response->assertOk();

        $feature = collect($response->json('features'))
            ->firstWhere('id', $entity->entity_id);

        $this->assertNotNull($feature);
        $this->assertSame('Polygon', $feature['geometry']['type'] ?? null);
    }
}
