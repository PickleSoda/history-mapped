<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ResolveOhmFeatureApiTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        // resolve-ohm-feature is an editorial geodata tool gated by
        // `permission:geometry.write`; authenticate as an authorised editor.
        $this->actingAs($this->userWithRole('admin'));
    }

    private function setEntityPointGeom(Entity $entity, float $lng, float $lat): void
    {
        $hasPrimary = DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->exists();

        if ($hasPrimary) {
            DB::statement(
                'UPDATE entity_locations
                 SET geom = ST_SetSRID(ST_MakePoint(?, ?), 4326), updated_at = NOW()
                 WHERE entity_id = ? AND is_primary = true',
                [$lng, $lat, $entity->entity_id],
            );

            return;
        }

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_SetSRID(ST_MakePoint(?, ?), 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true,
                NOW(), NOW()
            )",
            [$entity->entity_id, $lng, $lat],
        );
    }

    private function setEntityTerritoryGeom(Entity $entity): void
    {
        $hasPrimary = DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->exists();

        if ($hasPrimary) {
            DB::statement(
                "UPDATE entity_locations
                 SET territory_geom = ST_GeomFromText('POLYGON((10 40, 15 40, 15 45, 10 45, 10 40))', 4326),
                     updated_at = NOW()
                 WHERE entity_id = ? AND is_primary = true",
                [$entity->entity_id],
            );

            return;
        }

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, territory_geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_GeomFromText('POLYGON((10 40, 15 40, 15 45, 10 45, 10 40))', 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true,
                NOW(), NOW()
            )",
            [$entity->entity_id],
        );
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function insertGeoRef(Entity $entity, array $overrides = []): string
    {
        $geoRefId = $overrides['geo_ref_id'] ?? Str::uuid()->toString();

        DB::table('entity_geo_refs')->insert(array_merge([
            'geo_ref_id' => $geoRefId,
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '1880',
            'match_role' => 'candidate',
            'retrieval_method' => 'rest',
            'match_score' => 0.80,
            'is_active' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ], $overrides));

        return $geoRefId;
    }

    public function test_resolve_ohm_feature_prefers_active_primary_reference_and_returns_snapshot_geometry(): void
    {
        $primaryEntity = Entity::factory()->verified()->create(['name' => 'Roman Empire']);
        $secondaryEntity = Entity::factory()->verified()->create(['name' => 'Byzantine Empire']);

        $primaryGeoRefId = $this->insertGeoRef($primaryEntity, [
            'match_role' => 'primary',
            'match_score' => 0.70,
        ]);

        $this->insertGeoRef($secondaryEntity, [
            'match_role' => 'candidate',
            'match_score' => 0.99,
        ]);

        DB::table('entities')
            ->where('entity_id', $primaryEntity->entity_id)
            ->update(['primary_geo_ref_id' => $primaryGeoRefId]);

        $this->setEntityTerritoryGeom($primaryEntity);
        $this->setEntityPointGeom($primaryEntity, 12.5, 41.9);

        $response = $this->postJson(route('api.v1.map.resolve-ohm-feature'), [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '1880',
            'target_year' => 150,
        ]);

        $response->assertOk()
            ->assertJsonPath('data.entity.id', $primaryEntity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $primaryGeoRefId)
            ->assertJsonPath('data.feature_ref.provider', 'ohm')
            ->assertJsonPath('data.feature_ref.external_type', 'relation')
            ->assertJsonPath('data.feature_ref.external_id', '1880')
            ->assertJsonPath('data.feature_ref.target_year', 150)
            ->assertJsonPath('data.resolution_source', 'entity_location')
            ->assertJsonPath('data.geometry.type', 'Polygon');
    }

    public function test_resolve_ohm_feature_falls_back_to_base_entity_geometry(): void
    {
        $entity = Entity::factory()->verified()->create(['name' => 'Rome']);
        $geoRefId = $this->insertGeoRef($entity, [
            'external_type' => 'node',
            'external_id' => '999',
            'match_role' => 'primary',
        ]);

        DB::table('entities')
            ->where('entity_id', $entity->entity_id)
            ->update(['primary_geo_ref_id' => $geoRefId]);

        $this->setEntityPointGeom($entity, 12.4924, 41.8902);

        $response = $this->postJson(route('api.v1.map.resolve-ohm-feature'), [
            'provider' => 'ohm',
            'external_type' => 'node',
            'external_id' => '999',
            'target_year' => 117,
        ]);

        $response->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $geoRefId)
            ->assertJsonPath('data.feature_ref.provider', 'ohm')
            ->assertJsonPath('data.feature_ref.external_type', 'node')
            ->assertJsonPath('data.feature_ref.external_id', '999')
            ->assertJsonPath('data.feature_ref.target_year', 117)
            ->assertJsonPath('data.resolution_source', 'entity_location')
            ->assertJsonPath('data.geometry.type', 'Point');
    }

    public function test_resolve_ohm_feature_returns_period_specific_geometry_for_period_linked_georef(): void
    {
        $entity = Entity::factory()->verified()->create(['name' => 'Kingdom of Leon']);

        $periodA = GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => 978,
            'end_year' => 1064,
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[10, 40], [11, 40], [11, 41], [10, 40]]],
            ],
            'description' => 'Stage A',
            'provenance_mode' => 'ohm_import',
            'created_by' => 'test',
        ]);

        $periodB = GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => 1065,
            'end_year' => 1071,
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[20, 40], [21, 40], [21, 41], [20, 40]]],
            ],
            'description' => 'Stage B',
            'provenance_mode' => 'ohm_import',
            'created_by' => 'test',
        ]);

        $this->insertGeoRef($entity, [
            'external_id' => '200085109',
            'geometry_period_id' => $periodA->geometry_period_id,
            'temporal_start_year' => 978,
            'temporal_end_year' => 1064,
            'match_role' => 'candidate',
        ]);

        $this->insertGeoRef($entity, [
            'external_id' => '200085110',
            'geometry_period_id' => $periodB->geometry_period_id,
            'temporal_start_year' => 1065,
            'temporal_end_year' => 1071,
            'match_role' => 'candidate',
        ]);

        $responseA = $this->postJson(route('api.v1.map.resolve-ohm-feature'), [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '200085109',
            'target_year' => 1000,
        ]);

        $responseA->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.resolution_source', 'geometry_period')
            ->assertJsonPath('data.geometry.coordinates.0.0.0', 10);

        $responseB = $this->postJson(route('api.v1.map.resolve-ohm-feature'), [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '200085110',
            'target_year' => 1065,
        ]);

        $responseB->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.resolution_source', 'geometry_period')
            ->assertJsonPath('data.geometry.coordinates.0.0.0', 20);
    }

    public function test_resolve_ohm_feature_excludes_inactive_references(): void
    {
        $entity = Entity::factory()->verified()->create();

        $this->insertGeoRef($entity, [
            'external_id' => '555',
            'is_active' => false,
        ]);

        $this->postJson(route('api.v1.map.resolve-ohm-feature'), [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '555',
            'target_year' => 100,
        ])->assertNotFound();
    }
}
