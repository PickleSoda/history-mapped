<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;
use App\Models\User;

class GeometrySnapshotApiTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::factory()->create();
    }

    public function test_index_returns_snapshots_for_entity(): void
    {
        $entity = Entity::factory()->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(-27, 14)->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(14, 117)->create();

        $response = $this->getJson(route('api.v1.entities.geometry-snapshots.index', $entity));

        $response->assertOk();
        $this->assertCount(2, $response->json('data'));
    }

    public function test_at_year_returns_matching_snapshot(): void
    {
        $entity = Entity::factory()->create();

        GeometrySnapshot::factory()->forEntity($entity)->forYears(0, 100)->create([
            'display_priority' => 1,
        ]);

        $expected = GeometrySnapshot::factory()->forEntity($entity)->forYears(50, 80)->create([
            'display_priority' => 9,
            'label' => 'Preferred overlap',
        ]);

        $response = $this->getJson(route('api.v1.entities.geometry-snapshots.at-year', [
            'entity' => $entity,
            'year' => 60,
        ]));

        $response->assertOk()
            ->assertJsonPath('data.snapshot_id', $expected->snapshot_id)
            ->assertJsonPath('data.label', 'Preferred overlap');
    }

    public function test_store_can_attach_ohm_georef_and_hydrate_snapshot_geometry(): void
    {
        $entity = Entity::factory()->create();

        Http::fake([
            'https://nominatim.openhistoricalmap.org/lookup*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1880,
                    'display_name' => 'Roman Empire',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                    'extratags' => [
                        'historic' => 'empire',
                    ],
                ],
            ], 200),
        ]);

        $response = $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geometry-snapshots.store', $entity), [
                'year_start' => -27,
                'year_end' => 476,
                'label' => 'Imperial extent',
                'geography_reference' => [
                    'provider' => 'ohm',
                    'external_type' => 'relation',
                    'external_id' => '1880',
                    'match_role' => 'candidate',
                    'retrieval_method' => 'rest',
                    'match_score' => 0.95,
                ],
            ]);

        $response->assertCreated()
            ->assertJsonPath('data.label', 'Imperial extent')
            ->assertJsonPath('data.territory_geom.type', 'Polygon');

        $snapshotId = (string) $response->json('data.snapshot_id');
        $snapshot = GeometrySnapshot::query()->findOrFail($snapshotId);

        $this->assertNotNull($snapshot->geo_ref_id);
        $this->assertIsArray($snapshot->territory_geom);
        $this->assertSame('Polygon', $snapshot->territory_geom['type'] ?? null);

        $this->assertDatabaseHas('entity_geo_refs', [
            'geo_ref_id' => $snapshot->geo_ref_id,
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_id' => '1880',
        ]);
    }

    public function test_destroying_snapshot_keeps_entity_georef_available(): void
    {
        $entity = Entity::factory()->create();

        Http::fake([
            'https://nominatim.openhistoricalmap.org/lookup*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1880,
                    'display_name' => 'Roman Empire',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                ],
            ], 200),
        ]);

        $storeResponse = $this->actingAs($this->user)
            ->postJson(route('api.v1.entities.geometry-snapshots.store', $entity), [
                'year_start' => -27,
                'year_end' => 476,
                'label' => 'Imperial extent',
                'geography_reference' => [
                    'provider' => 'ohm',
                    'external_type' => 'relation',
                    'external_id' => '1880',
                    'match_role' => 'candidate',
                    'retrieval_method' => 'rest',
                    'match_score' => 0.95,
                ],
            ])
            ->assertCreated();

        $snapshotId = (string) $storeResponse->json('data.snapshot_id');
        $geoRefId = (string) $storeResponse->json('data.geo_ref_id');

        $this->actingAs($this->user)
            ->deleteJson(route('api.v1.entities.geometry-snapshots.destroy', [
                'entity' => $entity,
                'snapshot' => $snapshotId,
            ]))
            ->assertNoContent();

        $this->assertDatabaseMissing('geometry_snapshots', [
            'snapshot_id' => $snapshotId,
        ]);

        $this->assertDatabaseHas('entity_geo_refs', [
            'geo_ref_id' => $geoRefId,
            'entity_id' => $entity->entity_id,
        ]);
    }
}
