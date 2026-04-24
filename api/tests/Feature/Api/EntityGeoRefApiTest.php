<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class EntityGeoRefApiTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::factory()->create();
    }

    public function test_index_returns_geography_references_for_entity(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geography-references.store', $entity), [
                'provider' => 'ohm',
                'external_type' => 'relation',
                'external_id' => '12345',
                'match_role' => 'primary',
                'retrieval_method' => 'rest',
                'match_score' => 0.98,
            ])
            ->assertCreated();

        $response = $this->getJson(route('api.v1.entities.geography-references.index', $entity));

        $response->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.provider', 'ohm')
            ->assertJsonPath('data.0.external_type', 'relation')
            ->assertJsonPath('data.0.external_id', '12345')
            ->assertJsonPath('data.0.match_role', 'primary');
    }

    public function test_search_returns_ohm_candidates_with_metadata(): void
    {
        $entity = Entity::factory()->create();

        Http::fake([
            'https://nominatim.openhistoricalmap.org/search*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1880,
                    'display_name' => 'Roman Empire, Mediterranean',
                    'class' => 'boundary',
                    'type' => 'historic',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                    'extratags' => [
                        'name' => 'Roman Empire',
                        'historic' => 'empire',
                    ],
                    'lat' => '41.9',
                    'lon' => '12.5',
                ],
            ], 200),
        ]);

        $this->getJson(route('api.v1.entities.geography-references.search', [
            'entity' => $entity,
            'q' => 'Roman Empire',
            'location_name' => 'Mediterranean',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.external_type', 'relation')
            ->assertJsonPath('data.0.external_id', '1880')
            ->assertJsonPath('data.0.display_name', 'Roman Empire, Mediterranean')
            ->assertJsonPath('data.0.match_label', 'Roman Empire')
            ->assertJsonPath('data.0.external_tags.historic', 'empire')
            ->assertJsonPath('data.0.source_meta.class', 'boundary');
    }

    public function test_store_creates_geography_reference_and_sets_primary_pointer(): void
    {
        $entity = Entity::factory()->create();

        $response = $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geography-references.store', $entity), [
                'provider' => 'ohm',
                'external_type' => 'relation',
                'external_id' => '98765',
                'match_role' => 'primary',
                'retrieval_method' => 'rest',
                'temporal_start' => '-0027',
                'temporal_end' => '0476',
                'temporal_start_year' => -27,
                'temporal_end_year' => 476,
                'external_tags' => [
                    'boundary' => 'historic',
                ],
                'source_meta' => [
                    'label' => 'Roman Empire',
                ],
                'match_score' => 0.92,
                'is_active' => true,
            ]);

        $response->assertCreated()
            ->assertJsonPath('data.provider', 'ohm')
            ->assertJsonPath('data.external_id', '98765')
            ->assertJsonPath('data.match_role', 'primary')
            ->assertJsonPath('data.is_active', true);

        $this->assertDatabaseHas('entity_geo_refs', [
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '98765',
            'match_role' => 'primary',
            'is_active' => true,
        ]);

        $entity->refresh();
        $this->assertNotNull($entity->getAttribute('primary_geo_ref_id'));
    }

    public function test_delete_removes_reference_and_clears_primary_pointer(): void
    {
        $entity = Entity::factory()->create();

        $storeResponse = $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geography-references.store', $entity), [
                'provider' => 'ohm',
                'external_type' => 'relation',
                'external_id' => '444',
                'match_role' => 'primary',
                'retrieval_method' => 'rest',
                'match_score' => 0.81,
            ])
            ->assertCreated();

        $geoRefId = (string) $storeResponse->json('data.geo_ref_id');

        $this->actingAs($this->user)
            ->deleteJson(route('api.v1.entities.geography-references.destroy', [
                'entity' => $entity,
                'ref' => $geoRefId,
            ]))
            ->assertNoContent();

        $this->assertDatabaseMissing('entity_geo_refs', [
            'geo_ref_id' => $geoRefId,
        ]);

        $entity->refresh();
        $this->assertNull($entity->getAttribute('primary_geo_ref_id'));
    }

    public function test_store_fetches_ohm_metadata_and_hydrates_local_geometry(): void
    {
        $entity = Entity::factory()->create();

        Http::fake([
            'https://nominatim.openhistoricalmap.org/lookup*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 98765,
                    'display_name' => 'Roman Empire',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                    'extratags' => [
                        'historic' => 'empire',
                    ],
                    'lat' => '41.9',
                    'lon' => '12.5',
                ],
            ], 200),
        ]);

        $response = $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geography-references.store', $entity), [
                'provider' => 'ohm',
                'external_type' => 'relation',
                'external_id' => '98765',
                'match_role' => 'primary',
                'retrieval_method' => 'rest',
                'match_score' => 0.92,
            ]);

        $response->assertCreated()
            ->assertJsonPath('data.source_meta.display_name', 'Roman Empire')
            ->assertJsonPath('data.external_tags.historic', 'empire');

        $entity->refresh()->load('primaryLocation');

        $this->assertIsArray($entity->primaryLocation?->territory_geom);
        $this->assertSame('Polygon', $entity->primaryLocation?->territory_geom['type'] ?? null);
    }
}
