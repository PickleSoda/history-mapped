<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class EntityBuilderTemporalTest extends TestCase
{
    use RefreshDatabase;

    private function setPrimaryRange(Entity $entity, string $startDate, ?string $endDate): void
    {
        DB::table('entity_temporal_ranges')->insert([
            'entity_id' => $entity->entity_id,
            'start_date' => $startDate,
            'end_date' => $endDate,
            'is_primary' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    public function test_open_ended_entity_matches_exists_at_for_any_later_year(): void
    {
        $ongoing = Entity::factory()->verified()->create();
        $this->setPrimaryRange($ongoing, '1000-01-01', null); // end open = ongoing

        $closed = Entity::factory()->verified()->create();
        $this->setPrimaryRange($closed, '1000-01-01', '1100-01-01');

        $ids = Entity::query()->existsAt(1500)->pluck('entity_id')->all();

        $this->assertContains($ongoing->entity_id, $ids, 'ongoing entity should match any year after its start');
        $this->assertNotContains($closed->entity_id, $ids);
    }

    public function test_in_time_range_includes_open_ended(): void
    {
        $ongoing = Entity::factory()->verified()->create();
        $this->setPrimaryRange($ongoing, '1000-01-01', null);

        $ids = Entity::query()->inTimeRange(1400, 1450)->pluck('entity_id')->all();
        $this->assertContains($ongoing->entity_id, $ids);
    }
}
