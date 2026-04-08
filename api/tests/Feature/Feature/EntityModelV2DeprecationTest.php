<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EntityModelV2DeprecationTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::factory()->create();
        config()->set('entity_model.entity_model_v2_write_enabled', true);
    }

    public function test_create_writes_temporal_and_location_data_to_canonical_v2_tables(): void
    {
        $response = $this->actingAs($this->user)
            ->post(route('entities.store'), [
                'name' => 'Late Bronze Age polity',
                'entity_type' => EntityType::PoliticalEntity->value,
                'entity_group' => EntityGroup::Polity->value,
                'temporal_start' => '-1200',
                'temporal_end' => '-1100',
                'location_name' => 'Eastern Mediterranean',
                'location_method' => 'human_assigned',
                'geojson' => [
                    'type' => 'Point',
                    'coordinates' => [35.0, 33.0],
                ],
                'territory_geojson' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[34.0, 32.0], [36.0, 32.0], [36.0, 34.0], [34.0, 34.0], [34.0, 32.0]]],
                ],
            ]);

        $response->assertRedirect();

        $entity = Entity::query()->where('name', 'Late Bronze Age polity')->firstOrFail();

        $this->assertDatabaseHas('entity_temporal_ranges', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'start_year' => -1200,
            'end_year' => -1100,
        ]);

        $this->assertDatabaseHas('entity_locations', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'location_name' => 'Eastern Mediterranean',
        ]);
    }

    public function test_update_writes_temporal_and_location_data_to_canonical_v2_tables(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->putJson(route('api.v1.entities.update', $entity->entity_id), [
                'temporal_start' => '-0500',
                'temporal_end' => '-0450',
                'location_name' => 'Aegean basin',
                'location_method' => 'human_assigned',
                'geojson' => [
                    'type' => 'Point',
                    'coordinates' => [23.7, 37.9],
                ],
                'territory_geojson' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[22.0, 36.5], [25.0, 36.5], [25.0, 39.0], [22.0, 39.0], [22.0, 36.5]]],
                ],
            ])
            ->assertOk();

        $entity->refresh();

        $this->assertDatabaseHas('entity_temporal_ranges', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'start_year' => -500,
            'end_year' => -450,
        ]);

        $this->assertDatabaseHas('entity_locations', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'location_name' => 'Aegean basin',
        ]);
    }

    public function test_legacy_geometry_snapshot_write_endpoint_is_removed_when_v2_writes_enabled(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson("/entities/{$entity->entity_id}/geometry-snapshots", [
                'period_type' => 'territory',
                'start_year' => -80,
                'end_year' => -20,
                'provenance_mode' => 'manual',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
                ],
            ])
            ->assertStatus(404);
    }
}
