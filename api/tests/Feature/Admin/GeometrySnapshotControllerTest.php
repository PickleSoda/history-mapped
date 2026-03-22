<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    private Entity $entity;

    /** Minimal valid GeoJSON point geometry payload */
    private const POINT_GEOJSON = ['type' => 'Point', 'coordinates' => [12.4924, 41.8902]];

    /** FeatureCollection payload as produced by the map editor */
    private const POINTS_FEATURE_COLLECTION = [
        'type' => 'FeatureCollection',
        'features' => [
            [
                'type' => 'Feature',
                'properties' => [],
                'geometry' => [
                    'type' => 'Point',
                    'coordinates' => [10.0, 42.0],
                ],
            ],
            [
                'type' => 'Feature',
                'properties' => [],
                'geometry' => [
                    'type' => 'Point',
                    'coordinates' => [11.0, 43.0],
                ],
            ],
        ],
    ];

    /** Minimal valid GeoJSON polygon payload */
    private const POLYGON_GEOJSON = [
        'type' => 'Polygon',
        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
    ];

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
        $this->entity = Entity::factory()->create();
    }

    // ── index ─────────────────────────────────────────────────────────────────

    public function test_index_returns_empty_list_for_new_entity(): void
    {
        $this->actingAs($this->user)
            ->getJson(route('entities.snapshots.index', $this->entity))
            ->assertOk()
            ->assertJsonStructure(['snapshots'])
            ->assertJsonCount(0, 'snapshots');
    }

    public function test_index_returns_snapshots_for_entity(): void
    {
        GeometrySnapshot::factory()->forEntity($this->entity)->forYears(-27, 14)->create();
        GeometrySnapshot::factory()->forEntity($this->entity)->forYears(100, 200)->create();

        $this->actingAs($this->user)
            ->getJson(route('entities.snapshots.index', $this->entity))
            ->assertOk()
            ->assertJsonCount(2, 'snapshots');
    }

    public function test_index_does_not_return_snapshots_of_other_entity(): void
    {
        $other = Entity::factory()->create();
        GeometrySnapshot::factory()->forEntity($other)->create();

        $this->actingAs($this->user)
            ->getJson(route('entities.snapshots.index', $this->entity))
            ->assertOk()
            ->assertJsonCount(0, 'snapshots');
    }

    public function test_index_redirects_guests(): void
    {
        $this->getJson(route('entities.snapshots.index', $this->entity))
            ->assertUnauthorized();
    }

    // ── store ─────────────────────────────────────────────────────────────────

    public function test_store_creates_snapshot_with_point_geometry(): void
    {
        $response = $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => -27,
                'year_end' => 14,
                'geojson' => self::POINT_GEOJSON,
            ]);

        $response->assertCreated()
            ->assertJsonStructure(['snapshot' => ['snapshot_id', 'entity_id', 'year_start', 'year_end']]);

        $this->assertDatabaseHas('geometry_snapshots', [
            'entity_id' => $this->entity->entity_id,
            'year_start' => -27,
            'year_end' => 14,
        ]);
    }

    public function test_store_creates_snapshot_with_territory_geometry(): void
    {
        $response = $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 100,
                'year_end' => 200,
                'territory_geojson' => self::POLYGON_GEOJSON,
            ]);

        $response->assertCreated();

        $this->assertDatabaseHas('geometry_snapshots', [
            'entity_id' => $this->entity->entity_id,
            'year_start' => 100,
            'year_end' => 200,
        ]);
    }

    public function test_store_accepts_feature_collection_payloads(): void
    {
        $response = $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => -13,
                'year_end' => -9,
                'label' => 'chilling',
                'geojson' => self::POINTS_FEATURE_COLLECTION,
                'territory_geojson' => [
                    'type' => 'FeatureCollection',
                    'features' => [
                        [
                            'type' => 'Feature',
                            'properties' => [],
                            'geometry' => self::POLYGON_GEOJSON,
                        ],
                    ],
                ],
            ]);

        $response->assertCreated()
            ->assertJsonPath('snapshot.label', 'chilling');

        $this->assertDatabaseHas('geometry_snapshots', [
            'entity_id' => $this->entity->entity_id,
            'year_start' => -13,
            'year_end' => -9,
            'label' => 'chilling',
        ]);
    }

    public function test_store_persists_optional_metadata(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 0,
                'year_end' => 50,
                'label' => 'Maximum extent',
                'confidence' => 'high',
                'notes' => 'Source: Pliny',
                'display_priority' => 5,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertCreated()
            ->assertJsonPath('snapshot.label', 'Maximum extent')
            ->assertJsonPath('snapshot.confidence', 'high')
            ->assertJsonPath('snapshot.notes', 'Source: Pliny')
            ->assertJsonPath('snapshot.display_priority', 5);
    }

    public function test_store_requires_year_start(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_end' => 14,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['year_start']);
    }

    public function test_store_requires_year_end(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => -27,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['year_end']);
    }

    public function test_store_rejects_year_end_before_year_start(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 100,
                'year_end' => 50,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['year_end']);
    }

    public function test_store_requires_at_least_one_geometry(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 0,
                'year_end' => 50,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['geojson']);
    }

    public function test_store_rejects_invalid_confidence_value(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 0,
                'year_end' => 50,
                'confidence' => 'extreme',
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['confidence']);
    }

    public function test_store_rejects_geojson_with_wrong_type(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', $this->entity), [
                'year_start' => 0,
                'year_end' => 50,
                'geojson' => ['type' => 'Polygon', 'coordinates' => [[[0, 0], [1, 0], [1, 1], [0, 0]]]],
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['geojson.type']);
    }

    public function test_store_redirects_guests(): void
    {
        $this->postJson(route('entities.snapshots.store', $this->entity), [
            'year_start' => 0,
            'year_end' => 50,
            'geojson' => self::POINT_GEOJSON,
        ])->assertUnauthorized();
    }

    public function test_store_404s_for_unknown_entity(): void
    {
        $this->actingAs($this->user)
            ->postJson(route('entities.snapshots.store', '00000000-0000-0000-0000-000000000000'), [
                'year_start' => 0,
                'year_end' => 50,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertNotFound();
    }

    // ── update ────────────────────────────────────────────────────────────────

    public function test_update_modifies_snapshot(): void
    {
        $snapshot = GeometrySnapshot::factory()->forEntity($this->entity)->forYears(0, 100)->create();

        $this->actingAs($this->user)
            ->putJson(route('entities.snapshots.update', [$this->entity, $snapshot]), [
                'year_start' => 50,
                'year_end' => 150,
                'label' => 'Updated label',
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertOk()
            ->assertJsonPath('snapshot.year_start', 50)
            ->assertJsonPath('snapshot.year_end', 150)
            ->assertJsonPath('snapshot.label', 'Updated label');

        $this->assertDatabaseHas('geometry_snapshots', [
            'snapshot_id' => $snapshot->snapshot_id,
            'year_start' => 50,
            'year_end' => 150,
        ]);
    }

    public function test_update_rejects_snapshot_belonging_to_different_entity(): void
    {
        $other = Entity::factory()->create();
        $snapshot = GeometrySnapshot::factory()->forEntity($other)->forYears(0, 100)->create();

        $this->actingAs($this->user)
            ->putJson(route('entities.snapshots.update', [$this->entity, $snapshot]), [
                'year_start' => 0,
                'year_end' => 100,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertNotFound();
    }

    public function test_update_redirects_guests(): void
    {
        $snapshot = GeometrySnapshot::factory()->forEntity($this->entity)->forYears(0, 100)->create();

        $this->putJson(route('entities.snapshots.update', [$this->entity, $snapshot]), [
            'year_start' => 0,
            'year_end' => 100,
            'geojson' => self::POINT_GEOJSON,
        ])->assertUnauthorized();
    }

    public function test_update_404s_for_unknown_snapshot(): void
    {
        $this->actingAs($this->user)
            ->putJson(route('entities.snapshots.update', [$this->entity, '00000000-0000-0000-0000-000000000000']), [
                'year_start' => 0,
                'year_end' => 100,
                'geojson' => self::POINT_GEOJSON,
            ])
            ->assertNotFound();
    }

    // ── destroy ───────────────────────────────────────────────────────────────

    public function test_destroy_deletes_snapshot(): void
    {
        $snapshot = GeometrySnapshot::factory()->forEntity($this->entity)->forYears(0, 100)->create();

        $this->actingAs($this->user)
            ->deleteJson(route('entities.snapshots.destroy', [$this->entity, $snapshot]))
            ->assertNoContent();

        $this->assertDatabaseMissing('geometry_snapshots', [
            'snapshot_id' => $snapshot->snapshot_id,
        ]);
    }

    public function test_destroy_rejects_snapshot_belonging_to_different_entity(): void
    {
        $other = Entity::factory()->create();
        $snapshot = GeometrySnapshot::factory()->forEntity($other)->forYears(0, 100)->create();

        $this->actingAs($this->user)
            ->deleteJson(route('entities.snapshots.destroy', [$this->entity, $snapshot]))
            ->assertNotFound();
    }

    public function test_destroy_redirects_guests(): void
    {
        $snapshot = GeometrySnapshot::factory()->forEntity($this->entity)->forYears(0, 100)->create();

        $this->deleteJson(route('entities.snapshots.destroy', [$this->entity, $snapshot]))
            ->assertUnauthorized();
    }

    public function test_destroy_cascade_deletes_when_entity_is_deleted(): void
    {
        GeometrySnapshot::factory()->forEntity($this->entity)->forYears(0, 100)->create();
        GeometrySnapshot::factory()->forEntity($this->entity)->forYears(200, 300)->create();

        $entityId = $this->entity->entity_id;
        $this->entity->delete();

        $this->assertDatabaseMissing('geometry_snapshots', ['entity_id' => $entityId]);
    }

    public function test_destroy_404s_for_unknown_snapshot(): void
    {
        $this->actingAs($this->user)
            ->deleteJson(route('entities.snapshots.destroy', [$this->entity, '00000000-0000-0000-0000-000000000000']))
            ->assertNotFound();
    }
}
