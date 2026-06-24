<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EntityBackfillControllerTest extends TestCase
{
    use RefreshDatabase;

    /**
     * The core scenario: an entity with a primary location + temporal range but
     * no geometry periods is invisible on the map (the map reads geometry_periods).
     * Backfilling derives a territory geometry period so it becomes map-visible.
     */
    public function test_backfill_derives_geometry_period_from_primary_location(): void
    {
        $admin = $this->userWithRole('admin');

        $entity = Entity::factory()
            ->withTemporalRange('-0509', '-0027')
            ->atLocation('Rome')
            ->create();

        // Give the primary location a geometry — the factory's atLocation state
        // sets the name only.
        $entity->primaryLocation->update([
            'geom' => ['type' => 'Point', 'coordinates' => [12.48, 41.89]],
        ]);

        $this->assertDatabaseMissing('geometry_periods', [
            'entity_id' => $entity->entity_id,
        ]);

        $this->actingAs($admin)
            ->postJson(route('entities.backfill', $entity))
            ->assertOk()
            ->assertJsonPath('data.counts.geometry_periods', 1)
            ->assertJsonStructure([
                'data' => ['counts' => [
                    'aliases', 'tags', 'temporal_ranges', 'locations', 'geometry_periods',
                ]],
            ]);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -509,
            'end_year' => -27,
            'provenance_mode' => 'manual',
            'created_by' => 'backfill:entity',
        ]);
    }

    public function test_backfill_is_idempotent(): void
    {
        $admin = $this->userWithRole('admin');

        $entity = Entity::factory()
            ->withTemporalRange('-0509', '-0027')
            ->atLocation('Rome')
            ->create();
        $entity->primaryLocation->update([
            'geom' => ['type' => 'Point', 'coordinates' => [12.48, 41.89]],
        ]);

        $this->actingAs($admin)->postJson(route('entities.backfill', $entity))->assertOk();
        $this->actingAs($admin)->postJson(route('entities.backfill', $entity))->assertOk();

        // Re-running must not duplicate the derived territory period.
        $this->assertSame(
            1,
            (int) Entity::query()->whereKey($entity->entity_id)->first()
                ->geometryPeriods()->where('created_by', 'backfill:entity')->count(),
        );
    }

    /**
     * Bug fix (A): an entity with its own primary location but a stale, wrong
     * relationship-inference geometry period (from pipeline/backfill_geo.py) was
     * shown at the inferred — often wrong-continent — point on the map. Backfill
     * supersedes the low-confidence inferred period with the location-derived one.
     */
    public function test_backfill_supersedes_stale_relationship_inference_geometry(): void
    {
        $admin = $this->userWithRole('admin');

        $entity = Entity::factory()
            ->withTemporalRange('-0509', '-0027')
            ->atLocation('Rome')
            ->create();
        $entity->primaryLocation->update([
            'geom' => ['type' => 'Point', 'coordinates' => [12.48, 41.89]],
        ]);

        // Simulate the wrong inferred period (eastern Canada) from backfill_geo.py.
        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -509,
            'end_year' => -27,
            'geom' => ['type' => 'Point', 'coordinates' => [-66.85, 48.1]],
            'provenance_mode' => 'manual',
            'created_by' => 'geo-backfill:relationship_inference',
        ]);

        $this->actingAs($admin)
            ->postJson(route('entities.backfill', $entity))
            ->assertOk();

        // The stale inferred period is gone...
        $this->assertDatabaseMissing('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'created_by' => 'geo-backfill:relationship_inference',
        ]);

        // ...replaced by an authoritative location-derived territory period.
        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'created_by' => 'backfill:entity',
        ]);
    }

    public function test_backfill_keeps_inferred_geometry_when_no_own_location(): void
    {
        $admin = $this->userWithRole('admin');

        // No primary location → the inferred guess is the only signal; keep it.
        $entity = Entity::factory()->withTemporalRange('-0509', '-0027')->create();

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -509,
            'end_year' => -27,
            'geom' => ['type' => 'Point', 'coordinates' => [-66.85, 48.1]],
            'provenance_mode' => 'manual',
            'created_by' => 'geo-backfill:relationship_inference',
        ]);

        $this->actingAs($admin)
            ->postJson(route('entities.backfill', $entity))
            ->assertOk();

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'created_by' => 'geo-backfill:relationship_inference',
        ]);
    }

    public function test_backfill_requires_geometry_write_permission(): void
    {
        $user = $this->userWithPermissions([]);
        $entity = Entity::factory()->create();

        $this->actingAs($user)
            ->postJson(route('entities.backfill', $entity))
            ->assertForbidden();
    }
}
