<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::factory()->create();
    }

    public function test_legacy_admin_index_endpoint_is_removed(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->getJson("/entities/{$entity->entity_id}/geometry-snapshots")
            ->assertNotFound();
    }

    public function test_legacy_admin_store_endpoint_is_removed(): void
    {
        $entity = Entity::factory()->create();

        $this->actingAs($this->user)
            ->postJson("/entities/{$entity->entity_id}/geometry-snapshots", [
                'period_type' => 'presence',
                'start_year' => -44,
                'end_year' => -44,
                'provenance_mode' => 'manual',
                'geom' => [
                    'type' => 'Point',
                    'coordinates' => [12.5, 41.9],
                ],
            ])
            ->assertNotFound();
    }

    public function test_legacy_admin_update_and_destroy_endpoints_are_removed(): void
    {
        $entity = Entity::factory()->create();
        $snapshot = '00000000-0000-0000-0000-000000000000';

        $this->actingAs($this->user)
            ->putJson("/entities/{$entity->entity_id}/geometry-snapshots/{$snapshot}", [
                'period_type' => 'territory',
                'start_year' => -80,
                'end_year' => -20,
                'provenance_mode' => 'manual',
                'territory_geom' => [
                    'type' => 'Polygon',
                    'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
                ],
            ])
            ->assertNotFound();

        $this->actingAs($this->user)
            ->deleteJson("/entities/{$entity->entity_id}/geometry-snapshots/{$snapshot}")
            ->assertNotFound();
    }
}
