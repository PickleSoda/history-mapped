<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

/**
 * OHM tiles identify a feature only by a signed `osm_id` (spec D3): negative
 * is a relation, positive is a node or a way (node preferred). The resolver
 * accepts it as an alternative to `external_type` + `external_id`.
 */
class ResolveOhmFeatureSignedIdTest extends TestCase
{
    use RefreshDatabase;

    private function insertGeoRef(Entity $entity, string $externalType, string $externalId, float $matchScore = 0.90): string
    {
        $geoRefId = Str::uuid()->toString();

        DB::table('entity_geo_refs')->insert([
            'geo_ref_id' => $geoRefId,
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => $externalType,
            'external_id' => $externalId,
            'match_role' => 'primary',
            'retrieval_method' => 'rest',
            'match_score' => $matchScore,
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

    /**
     * @return array{0: Entity, 1: string} the entity and its geo-ref id
     */
    private function linkedEntity(string $name, string $externalType, string $externalId, float $matchScore = 0.90): array
    {
        $entity = Entity::factory()->verified()->create(['name' => $name]);
        $geoRefId = $this->insertGeoRef($entity, $externalType, $externalId, $matchScore);
        $this->setEntityPointGeom($entity, 12.4924, 41.8902);

        return [$entity, $geoRefId];
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private function resolve(array $params): TestResponse
    {
        return $this->getJson(route('api.v1.map.resolve-ohm-feature.show', $params));
    }

    public function test_negative_osm_id_resolves_a_relation_ref(): void
    {
        [$entity, $geoRefId] = $this->linkedEntity('Roman Empire', 'relation', '1880');

        $this->resolve(['osm_id' => -1880, 'provider' => 'ohm', 'target_year' => 117])
            ->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $geoRefId)
            ->assertJsonPath('data.feature_ref.external_type', 'relation')
            ->assertJsonPath('data.feature_ref.external_id', '1880');
    }

    public function test_positive_osm_id_resolves_a_node_ref(): void
    {
        [$entity, $geoRefId] = $this->linkedEntity('Rome', 'node', '42');

        $this->resolve(['osm_id' => 42, 'provider' => 'ohm', 'target_year' => 117])
            ->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $geoRefId)
            ->assertJsonPath('data.feature_ref.external_type', 'node')
            ->assertJsonPath('data.feature_ref.external_id', '42');
    }

    public function test_positive_osm_id_resolves_a_way_ref_when_no_node_ref_exists(): void
    {
        [$entity, $geoRefId] = $this->linkedEntity('Hadrian\'s Wall', 'way', '42');

        $this->resolve(['osm_id' => 42, 'provider' => 'ohm', 'target_year' => 117])
            ->assertOk()
            ->assertJsonPath('data.entity.id', $entity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $geoRefId)
            ->assertJsonPath('data.feature_ref.external_type', 'way')
            ->assertJsonPath('data.feature_ref.external_id', '42');
    }

    public function test_positive_osm_id_prefers_the_node_ref_over_a_way_ref(): void
    {
        // The way ref scores higher, so without the node-first preference it
        // would win the existing match_score ordering.
        [$nodeEntity, $nodeGeoRefId] = $this->linkedEntity('Rome', 'node', '42', 0.50);
        $this->linkedEntity('Hadrian\'s Wall', 'way', '42', 0.95);

        $this->resolve(['osm_id' => 42, 'provider' => 'ohm', 'target_year' => 117])
            ->assertOk()
            ->assertJsonPath('data.entity.id', $nodeEntity->entity_id)
            ->assertJsonPath('data.geo_ref_id', $nodeGeoRefId)
            ->assertJsonPath('data.feature_ref.external_type', 'node');
    }

    public function test_zero_osm_id_is_rejected(): void
    {
        foreach ([0, '-0', '+0'] as $zero) {
            $this->resolve(['osm_id' => $zero, 'provider' => 'ohm', 'target_year' => 117])
                ->assertUnprocessable()
                ->assertJsonValidationErrors(['osm_id']);
        }
    }

    public function test_sign_selects_the_ref_type(): void
    {
        // Only a relation/42 exists: a positive id (node or way) must not find it,
        // and a negative id must not find a node/42.
        $this->linkedEntity('Relation Only', 'relation', '42');
        $this->linkedEntity('Node Only', 'node', '7');

        $this->resolve(['osm_id' => 42, 'provider' => 'ohm', 'target_year' => 117])->assertNotFound();
        $this->resolve(['osm_id' => -7, 'provider' => 'ohm', 'target_year' => 117])->assertNotFound();
    }

    public function test_osm_id_together_with_external_id_is_rejected(): void
    {
        $this->linkedEntity('Roman Empire', 'relation', '1880');

        $this->resolve([
            'osm_id' => -1880,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '1880',
            'target_year' => 117,
        ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['external_id']);
    }

    public function test_osm_id_together_with_external_type_is_rejected(): void
    {
        $this->linkedEntity('Roman Empire', 'relation', '1880');

        $this->resolve([
            'osm_id' => -1880,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'target_year' => 117,
        ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['external_type']);
    }

    public function test_omitting_both_osm_id_and_external_id_is_rejected(): void
    {
        $this->resolve(['provider' => 'ohm', 'target_year' => 117])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['osm_id', 'external_id']);
    }
}
