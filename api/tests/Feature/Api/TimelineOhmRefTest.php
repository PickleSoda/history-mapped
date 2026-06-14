<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Actions\Timeline\ProjectEntityTimelineAction;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class TimelineOhmRefTest extends TestCase
{
    use RefreshDatabase;

    private function seedTimeline(Entity $entity): void
    {
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', 900, 1100,
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id],
        );

        app(ProjectEntityTimelineAction::class)->rebuildForEntity($entity->entity_id);
    }

    public function test_timeline_entries_carry_ohm_ref_for_linked_entity(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->seedTimeline($entity);

        DB::statement(
            "INSERT INTO entity_geo_refs (
                geo_ref_id, entity_id, external_id, external_type, provider,
                match_role, retrieval_method, is_active, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'R456', 'relation', 'ohm', 'primary', 'manual', true, NOW(), NOW()
            )",
            [$entity->entity_id],
        );

        $response = $this->getJson(route('api.v1.entities.timeline.index', $entity->entity_id));

        $response->assertOk();
        $entries = $response->json('data');
        $this->assertNotEmpty($entries);

        foreach ($entries as $entry) {
            $this->assertSame('R456', $entry['ohm_external_id']);
            $this->assertSame('relation', $entry['ohm_external_type']);
            $this->assertSame('ohm', $entry['ohm_provider']);
        }
    }

    public function test_timeline_entries_have_null_ohm_ref_for_unlinked_entity(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->seedTimeline($entity);

        $response = $this->getJson(route('api.v1.entities.timeline.index', $entity->entity_id));

        $response->assertOk();
        $entries = $response->json('data');
        $this->assertNotEmpty($entries);

        foreach ($entries as $entry) {
            $this->assertNull($entry['ohm_external_id']);
            $this->assertNull($entry['ohm_external_type']);
            $this->assertNull($entry['ohm_provider']);
        }
    }
}
