<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * The public atlas resolves an OHM basemap feature to an entity via a
 * read-only GET (no auth) — distinct from the editor's gated POST.
 */
class ResolveOhmFeaturePublicApiTest extends TestCase
{
    use RefreshDatabase;

    private function insertGeoRef(Entity $entity, string $externalId): string
    {
        $geoRefId = Str::uuid()->toString();

        DB::table('entity_geo_refs')->insert([
            'geo_ref_id' => $geoRefId,
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => $externalId,
            'match_role' => 'primary',
            'retrieval_method' => 'rest',
            'match_score' => 0.90,
            'is_active' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        DB::table('entities')
            ->where('entity_id', $entity->entity_id)
            ->update(['primary_geo_ref_id' => $geoRefId]);

        return $geoRefId;
    }

    private function setEntityPointGeom(Entity $entity, float $lng, float $lat): void
    {
        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_SetSRID(ST_MakePoint(?, ?), 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true, NOW(), NOW()
            )",
            [$entity->entity_id, $lng, $lat],
        );
    }

    public function test_public_get_resolves_ohm_feature_without_auth(): void
    {
        $entity = Entity::factory()->verified()->create(['name' => 'Rome']);
        $geoRefId = $this->insertGeoRef($entity, '1880');
        $this->setEntityPointGeom($entity, 12.4924, 41.8902);

        $response = $this->getJson(route('api.v1.map.resolve-ohm-feature.show', [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '1880',
            'target_year' => 117,
        ]));

        $response->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $geoRefId)
            ->assertJsonPath('data.feature_ref.external_id', '1880')
            ->assertJsonPath('data.geometry.type', 'Point');
    }

    public function test_public_get_returns_404_when_no_match(): void
    {
        $this->getJson(route('api.v1.map.resolve-ohm-feature.show', [
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => 'does-not-exist',
            'target_year' => 100,
        ]))->assertNotFound();
    }
}
