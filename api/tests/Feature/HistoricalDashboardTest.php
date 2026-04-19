<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class HistoricalDashboardTest extends TestCase
{
    use RefreshDatabase;

    private function setGeom(Entity $entity, float $lng = 12.5, float $lat = 41.9): void
    {
        DB::table('entity_locations')
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom,
                location_method, location_confidence, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, NULL,
                ST_SetSRID(ST_Point(?, ?), 4326),
                'human_assigned'::location_resolution_method,
                'high'::confidence_level,
                true,
                NOW(),
                NOW()
            )",
            [$entity->entity_id, $lng, $lat],
        );
    }

    public function test_authenticated_user_can_view_dashboard(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user);

        $this->get(route('dashboard'))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('dashboard'));
    }

    public function test_dashboard_map_endpoint_returns_entities_for_a_requested_year(): void
    {
        $entity = Entity::factory()
            ->verified()
            ->withTemporalRange('950', '1050')
            ->create();

        $this->setGeom($entity);

        $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ]))
            ->assertOk()
            ->assertJsonStructure([
                'type',
                'features' => [
                    '*' => ['type', 'id', 'geometry', 'properties'],
                ],
            ]);
    }

    public function test_unauthenticated_user_cannot_view_dashboard(): void
    {
        $this->get(route('dashboard'))
            ->assertRedirect(route('login'));
    }
}
