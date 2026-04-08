<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Jobs\RebuildEntityTimelineJob;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Str;
use Tests\TestCase;

class RebuildEntityTimelineCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_rebuild_command_uses_primary_temporal_range_when_geometry_periods_are_missing(): void
    {
        $entity = Entity::factory()->create(['name' => 'Late Republic']);

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_year' => -133,
            'end_year' => -27,
            'is_primary' => true,
            'notes' => 'Conventional late republican dating.',
        ]);

        $this->artisan('timeline:rebuild', ['entity_id' => $entity->entity_id])->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $entity->entity_id,
            'entry_kind' => 'temporal_range',
            'source_table' => 'entity_temporal_ranges',
            'start_year' => -133,
            'end_year' => -27,
            'title' => 'Primary temporal range',
        ]);
    }

    public function test_rebuild_command_projects_all_temporal_ranges_when_geometry_periods_are_missing(): void
    {
        $entity = Entity::factory()->create(['name' => 'Roman Republic']);

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_year' => -509,
            'end_year' => -27,
            'is_primary' => true,
            'notes' => 'Primary span',
        ]);

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'phase',
            'start_year' => -133,
            'end_year' => -27,
            'is_primary' => false,
            'notes' => 'Late republican phase',
        ]);

        $this->artisan('timeline:rebuild', ['entity_id' => $entity->entity_id])->assertExitCode(0);

        $this->assertDatabaseCount('entity_timeline_entries', 2);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $entity->entity_id,
            'entry_kind' => 'temporal_range',
            'source_table' => 'entity_temporal_ranges',
            'start_year' => -509,
            'end_year' => -27,
            'title' => 'Primary temporal range',
        ]);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $entity->entity_id,
            'entry_kind' => 'temporal_range',
            'source_table' => 'entity_temporal_ranges',
            'start_year' => -133,
            'end_year' => -27,
            'title' => 'Temporal range',
        ]);
    }

    public function test_rebuild_command_projects_denormalized_relationship_fields(): void
    {
        $person = Entity::factory()->create(['name' => 'Julius Caesar']);
        $battle = Entity::factory()->create(['name' => 'Battle of Pharsalus']);

        $relationshipId = Str::uuid()->toString();

        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $person->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'victorious_at',
            'temporal_start' => '-0048',
            'temporal_end' => '-0048',
            'start_year' => -48,
            'end_year' => -48,
            'description' => 'Caesar defeats Pompey.',
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, relationship_id, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'presence', -48, -48,
                ST_SetSRID(ST_MakePoint(22.5, 39.2), 4326), 'derived', ?, 'test', NOW(), NOW()
            )",
            [Str::uuid()->toString(), $person->entity_id, $relationshipId],
        );

        $this->artisan('timeline:rebuild', ['entity_id' => $person->entity_id])->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $person->entity_id,
            'relationship_type' => 'victorious_at',
            'related_entity_id' => $battle->entity_id,
            'related_entity_name' => 'Battle of Pharsalus',
            'start_year' => -48,
            'end_year' => -48,
        ]);
    }

    public function test_geometry_period_mutations_trigger_targeted_rebuild(): void
    {
        Queue::fake();

        $person = Entity::factory()->create(['name' => 'Julius Caesar']);
        $battle = Entity::factory()->create(['name' => 'Siege of Alesia']);

        $relationshipId = Str::uuid()->toString();

        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $person->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'victorious_at',
            'temporal_start' => '-0052',
            'temporal_end' => '-0052',
            'start_year' => -52,
            'end_year' => -52,
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        $period = new GeometryPeriod([
            'entity_id' => $person->entity_id,
            'period_type' => 'presence',
            'start_year' => -52,
            'end_year' => -52,
            'provenance_mode' => 'derived',
            'relationship_id' => $relationshipId,
            'description' => 'Initial period',
            'created_by' => 'test',
            'geom' => [
                'type' => 'Point',
                'coordinates' => [4.5, 47.5],
            ],
        ]);
        $period->save();

        Queue::assertPushed(RebuildEntityTimelineJob::class, function (RebuildEntityTimelineJob $job) use ($person): bool {
            return $job->entityId === $person->entity_id;
        });

        $period->description = 'Updated period description';
        $period->save();

        Queue::assertPushed(RebuildEntityTimelineJob::class, function (RebuildEntityTimelineJob $job) use ($person): bool {
            return $job->entityId === $person->entity_id;
        });

        $period->delete();

        Queue::assertPushed(RebuildEntityTimelineJob::class, 3);
    }
}
