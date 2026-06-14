<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Actions\Timeline\ProjectEntityTimelineAction;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class TimelineProjectionTest extends TestCase
{
    use RefreshDatabase;

    public function test_open_start_range_projects_a_span_without_crashing(): void
    {
        $entity = Entity::factory()->verified()->create();

        // Only temporal info: an open-START range (start_year NULL, end_year 1200).
        DB::table('entity_temporal_ranges')->insert([
            'entity_id' => $entity->entity_id,
            'start_year' => null,
            'start_date' => null,
            'end_year' => 1200,
            'end_date' => '1200-01-01',
            'is_primary' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $action = app(ProjectEntityTimelineAction::class);
        $action->rebuildForEntity($entity->entity_id);

        // The NOT NULL start_year is coalesced from end_year — no crash, span at 1200.
        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $entity->entity_id,
            'start_year' => 1200,
        ]);
    }
}
