<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ResolveOhmFeatureApiTest extends TestCase
{
    use RefreshDatabase;

    private function setEntityPointGeom(Entity $entity, float $lng, float $lat): void
    {
        $hasPrimary = DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->exists();

        if ($hasPrimary) {
            DB::statement(
                "UPDATE entity_locations
                 SET geom = ST_SetSRID(ST_MakePoint(?, ?), 4326), updated_at = NOW()
                 WHERE entity_id = ? AND is_primary = true",
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
            ->assertJsonPath('data.resolution_source', 'entity_geom')
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
            ->assertJsonPath('data.resolution_source', 'entity_geom')
            ->assertJsonPath('data.geometry.type', 'Point');
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

