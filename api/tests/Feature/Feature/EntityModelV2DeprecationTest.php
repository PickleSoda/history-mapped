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

    public function test_create_does_not_write_legacy_temporal_or_location_columns_when_v2_writes_enabled(): void
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
            ]);

        $response->assertRedirect();

        $entity = Entity::query()->where('name', 'Late Bronze Age polity')->firstOrFail();

        $this->assertNull($entity->temporal_start);
        $this->assertNull($entity->temporal_end);
        $this->assertNull($entity->temporal_start_year);
        $this->assertNull($entity->temporal_end_year);
        $this->assertNull($entity->location_name);
    }

    public function test_update_does_not_mutate_legacy_temporal_or_location_columns_when_v2_writes_enabled(): void
    {
        $entity = Entity::factory()->create([
            'temporal_start' => null,
            'temporal_end' => null,
            'temporal_start_year' => null,
            'temporal_end_year' => null,
            'location_name' => null,
        ]);

        $this->actingAs($this->user)
            ->putJson(route('api.v1.entities.update', $entity->entity_id), [
                'temporal_start' => '-0500',
                'temporal_end' => '-0450',
                'location_name' => 'Aegean basin',
                'location_method' => 'human_assigned',
            ])
            ->assertOk();

        $entity->refresh();

        $this->assertNull($entity->temporal_start);
        $this->assertNull($entity->temporal_end);
        $this->assertNull($entity->temporal_start_year);
        $this->assertNull($entity->temporal_end_year);
        $this->assertNull($entity->location_name);
    }

    public function test_legacy_geometry_snapshot_write_endpoint_is_disabled_when_v2_writes_enabled(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson(route('entities.geometry-snapshots.store', $entity), [
                'period_type' => 'territory',
                'start_year' => -80,
                'end_year' => -20,
                'provenance_mode' => 'manual',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
                ],
            ])
            ->assertStatus(410);
    }
}
