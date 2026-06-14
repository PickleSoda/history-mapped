<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesByYearOhmRefTest extends TestCase
{
    use RefreshDatabase;

    public function test_year_endpoint_emits_ohm_ref_and_point_geometry(): void
    {
        $entity = Entity::factory()->verified()->create();

        // A period with BOTH a point and a polygon, active at the queried year.
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_Point(10.5, 40.5), 4326),
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id],
        );

        // An active OHM geo-ref for the entity.
        DB::statement(
            "INSERT INTO entity_geo_refs (
                geo_ref_id, entity_id, external_id, external_type, provider,
                match_role, retrieval_method, is_active, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'R123', 'relation', 'ohm', 'primary', 'manual', true, NOW(), NOW()
            )",
            [$entity->entity_id],
        );

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
        ]));

        $response->assertOk();
        $feature = collect($response->json('features'))->firstWhere('id', $entity->entity_id);

        $this->assertNotNull($feature);
        $this->assertSame('R123', $feature['properties']['ohm_external_id']);
        $this->assertSame('relation', $feature['properties']['ohm_external_type']);
        $this->assertSame('ohm', $feature['properties']['ohm_provider']);
        // OHM-linked entities serialize the point, not the polygon.
        $this->assertSame('Point', $feature['geometry']['type']);
    }

    public function test_year_endpoint_emits_null_ohm_ref_for_unlinked_entity(): void
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

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
        ]));

        $response->assertOk();
        $feature = collect($response->json('features'))->firstWhere('id', $entity->entity_id);

        $this->assertNotNull($feature);
        $this->assertNull($feature['properties']['ohm_provider']);
        $this->assertNull($feature['properties']['ohm_external_id']);
        $this->assertNull($feature['properties']['ohm_external_type']);
    }
}
