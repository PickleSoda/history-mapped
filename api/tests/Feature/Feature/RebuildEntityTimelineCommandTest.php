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
            'start_date' => '-0133',
            'end_date' => '-0027',
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
            'start_date' => '-0509',
            'end_date' => '-0027',
            'is_primary' => true,
            'notes' => 'Primary span',
        ]);

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'phase',
            'start_date' => '-0133',
            'end_date' => '-0027',
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

    public function test_rebuild_command_projects_relationship_only_entries_for_incoming_relationships(): void
    {
        $source = Entity::factory()->create(['name' => 'Mongol Empire']);
        $target = Entity::factory()->create(['name' => 'Song Dynasty']);

        DB::table('relationships')->insert([
            'relationship_id' => Str::uuid()->toString(),
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'at_war_with',
            'temporal_start' => '1234',
            'temporal_end' => '1279',
            'start_year' => 1234,
            'end_year' => 1279,
            'description' => 'Conflict period',
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        $this->artisan('timeline:rebuild', ['entity_id' => $target->entity_id])->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $target->entity_id,
            'entry_kind' => 'relationship',
            'source_table' => 'relationships',
            'title' => 'Mongol Empire',
            'description' => 'Conflict period',
            'relationship_type' => 'at_war_with',
            'related_entity_id' => $source->entity_id,
            'related_entity_name' => 'Mongol Empire',
            'start_year' => 1234,
            'end_year' => 1279,
        ]);
    }

    public function test_global_rebuild_includes_entities_with_incoming_relationships_only(): void
    {
        $source = Entity::factory()->create(['name' => 'Mongol Empire']);
        $target = Entity::factory()->create(['name' => 'Khwarazmian Empire']);

        DB::table('relationships')->insert([
            'relationship_id' => Str::uuid()->toString(),
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'at_war_with',
            'temporal_start' => '1219',
            'temporal_end' => '1221',
            'start_year' => 1219,
            'end_year' => 1221,
            'description' => 'Mongol invasion of Khwarazmia',
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        $this->artisan('timeline:rebuild')->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $target->entity_id,
            'entry_kind' => 'relationship',
            'source_table' => 'relationships',
            'title' => 'Mongol Empire',
            'description' => 'Mongol invasion of Khwarazmia',
            'relationship_type' => 'at_war_with',
            'related_entity_id' => $source->entity_id,
            'related_entity_name' => 'Mongol Empire',
            'start_year' => 1219,
            'end_year' => 1221,
        ]);
    }

    public function test_rebuild_command_keeps_incoming_relationship_row_when_geometry_period_exists_for_source_entity(): void
    {
        $source = Entity::factory()->create(['name' => 'Mongol Empire']);
        $target = Entity::factory()->create(['name' => 'Song Dynasty']);
        $relationshipId = Str::uuid()->toString();

        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'at_war_with',
            'temporal_start' => '1234',
            'temporal_end' => '1279',
            'start_year' => 1234,
            'end_year' => 1279,
            'description' => 'Conflict period',
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, relationship_id, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'presence', 1234, 1279,
                ST_SetSRID(ST_MakePoint(110.0, 40.0), 4326), 'derived', ?, 'test', NOW(), NOW()
            )",
            [Str::uuid()->toString(), $source->entity_id, $relationshipId],
        );

        $this->artisan('timeline:rebuild', ['entity_id' => $target->entity_id])->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $target->entity_id,
            'entry_kind' => 'relationship',
            'source_table' => 'relationships',
            'source_id' => $relationshipId,
            'relationship_type' => 'at_war_with',
            'related_entity_id' => $source->entity_id,
            'related_entity_name' => 'Mongol Empire',
            'start_year' => 1234,
            'end_year' => 1279,
        ]);
    }

    public function test_rebuild_command_projects_primary_point_for_incoming_relationship_rows(): void
    {
        $source = Entity::factory()->create(['name' => 'Cornish Tin']);
        $target = Entity::factory()->create(['name' => 'Roman Empire']);
        $relationshipId = Str::uuid()->toString();

        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'allied_with',
            'temporal_start' => '-0050',
            'temporal_end' => '0001',
            'start_year' => -50,
            'end_year' => 1,
            'description' => 'Tin trade to Roman markets',
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        DB::statement(
            "INSERT INTO entity_locations (
                location_id, entity_id, location_name, geom, is_primary, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'Cornwall', ST_SetSRID(ST_MakePoint(-5.0, 50.0), 4326), true, NOW(), NOW()
            )",
            [$source->entity_id],
        );

        $this->artisan('timeline:rebuild', ['entity_id' => $target->entity_id])->assertExitCode(0);

        $timelineRow = DB::table('entity_timeline_entries')
            ->where('entity_id', $target->entity_id)
            ->where('source_table', 'relationships')
            ->where('source_id', $relationshipId)
            ->selectRaw('ST_GeometryType(geom) as geom_type')
            ->selectRaw('ST_X(geom) as geom_x')
            ->selectRaw('ST_Y(geom) as geom_y')
            ->selectRaw('territory_geom IS NULL as territory_geom_is_null')
            ->first();

        $this->assertNotNull($timelineRow);
        $this->assertSame('ST_Point', $timelineRow->geom_type);
        $this->assertEqualsWithDelta(-5.0, (float) $timelineRow->geom_x, 0.00001);
        $this->assertEqualsWithDelta(50.0, (float) $timelineRow->geom_y, 0.00001);
        $this->assertTrue((bool) $timelineRow->territory_geom_is_null);
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
