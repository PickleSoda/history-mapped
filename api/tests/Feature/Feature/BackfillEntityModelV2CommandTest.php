<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use App\Models\EntityTimelineEntry;
use App\Models\EntityLocation;
use App\Models\EntityTemporalRange;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Str;
use Tests\TestCase;

class BackfillEntityModelV2CommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_backfill_command_is_safe_with_existing_canonical_rows(): void
    {
        $entity = Entity::factory()->create();

        \App\Models\EntityAlias::query()->create([
            'entity_id' => $entity->entity_id,
            'name' => 'Imperium Romanum',
            'is_primary' => false,
        ]);

        \App\Models\EntityAlias::query()->create([
            'entity_id' => $entity->entity_id,
            'name' => 'Res Publica Romana',
            'is_primary' => false,
        ]);

        \App\Models\EntityTag::query()->create([
            'entity_id' => $entity->entity_id,
            'tag' => 'rome',
        ]);

        \App\Models\EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_year' => -509,
            'end_year' => -27,
            'start_date' => '-0509',
            'end_date' => '-0027',
            'is_primary' => true,
        ]);

        \App\Models\EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => 'Rome',
            'is_primary' => true,
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $this->assertDatabaseHas('entity_aliases', [
            'entity_id' => $entity->entity_id,
            'name' => 'Imperium Romanum',
        ]);

        $this->assertDatabaseHas('entity_aliases', [
            'entity_id' => $entity->entity_id,
            'name' => 'Res Publica Romana',
        ]);

        $this->assertDatabaseHas('entity_tags', [
            'entity_id' => $entity->entity_id,
            'tag' => 'rome',
        ]);

        $this->assertDatabaseHas('entity_temporal_ranges', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'start_year' => -509,
            'end_year' => -27,
            'start_date' => '-0509',
            'end_date' => '-0027',
        ]);

        $this->assertDatabaseHas('entity_locations', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'location_name' => 'Rome',
        ]);
    }

    public function test_backfill_command_supports_dry_run_without_writing(): void
    {
        $entity = Entity::factory()->create();

        $this->artisan('entity-model-v2:backfill --dry-run')
            ->expectsOutputToContain('[DRY-RUN] Entity Model V2 backfill summary')
            ->assertExitCode(0);

        $this->assertDatabaseMissing('entity_aliases', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_tags', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_temporal_ranges', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_locations', ['entity_id' => $entity->entity_id]);
    }

    public function test_database_seeder_runs_backfill_for_canonical_v2_tables(): void
    {
        $this->seed(\Database\Seeders\DatabaseSeeder::class);

        $entity = Entity::query()->where('name', 'Roman Empire')->firstOrFail();

        $this->assertDatabaseHas('entity_aliases', [
            'entity_id' => $entity->entity_id,
            'name' => 'Imperium Romanum',
        ]);

        $this->assertDatabaseHas('entity_tags', [
            'entity_id' => $entity->entity_id,
            'tag' => 'rome',
        ]);

        $this->assertDatabaseHas('entity_temporal_ranges', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
        ]);

        $this->assertDatabaseHas('entity_locations', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'location_name' => 'Rome, Italia',
        ]);
    }

    public function test_factory_temporal_and_location_states_create_canonical_v2_rows(): void
    {
        $entity = Entity::factory()
            ->withTemporalRange('-0509', '-0027')
            ->atLocation('Rome')
            ->create();

        $this->assertDatabaseHas('entity_temporal_ranges', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'start_year' => -509,
            'end_year' => -27,
            'start_date' => '-0509',
            'end_date' => '-0027',
        ]);

        $this->assertDatabaseHas('entity_locations', [
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'location_name' => 'Rome',
        ]);
    }

    public function test_backfill_command_creates_geometry_periods_from_temporal_ranges_and_geometry(): void
    {
        $entity = Entity::factory()->create();

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_date' => '-0509',
            'end_date' => '-0027',
            'is_primary' => true,
            'notes' => 'Republican period',
        ]);

        EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => 'Rome',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [12.4964, 41.9028],
            ],
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -509,
            'end_year' => -27,
            'provenance_mode' => 'manual',
            'created_by' => 'backfill:entity-model-v2',
        ]);
    }

    public function test_backfill_command_creates_derived_presence_periods_from_relationships_with_temporal_fallback(): void
    {
        $source = Entity::factory()->create();
        $target = Entity::factory()->create();
        $relationshipId = (string) Str::uuid();

        EntityTemporalRange::query()->create([
            'entity_id' => $source->entity_id,
            'range_type' => 'primary',
            'start_date' => '-0100',
            'end_date' => '-0090',
            'is_primary' => true,
        ]);

        EntityLocation::query()->create([
            'entity_id' => $source->entity_id,
            'location_name' => 'Test Place',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [10.0, 45.0],
            ],
        ]);

        EntityRelationship::query()->create([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'contributed_to',
            'created_by' => 'test',
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $source->entity_id,
            'period_type' => 'presence',
            'relationship_id' => $relationshipId,
            'start_year' => -100,
            'end_year' => -90,
            'provenance_mode' => 'derived',
            'created_by' => 'backfill:entity-model-v2',
        ]);
    }

    public function test_backfill_command_rebuilds_timeline_entries_synchronously(): void
    {
        Queue::fake();

        $entity = Entity::factory()->create();

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_date' => '-0050',
            'end_date' => '-0040',
            'is_primary' => true,
        ]);

        EntityLocation::query()->create([
            'entity_id' => $entity->entity_id,
            'location_name' => 'Timeline Place',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [12.0, 42.0],
            ],
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $entry = EntityTimelineEntry::query()
            ->where('entity_id', $entity->entity_id)
            ->where('source_table', 'geometry_periods')
            ->first();

        $this->assertNotNull($entry);
        $this->assertSame('territory_period', $entry->entry_kind);
    }

    public function test_backfill_command_projects_derived_presence_periods_for_source_entity_when_relationship_is_incoming_to_another_entity(): void
    {
        $source = Entity::factory()->create();
        $target = Entity::factory()->create();
        $relationshipId = (string) Str::uuid();

        EntityTemporalRange::query()->create([
            'entity_id' => $source->entity_id,
            'range_type' => 'primary',
            'start_date' => '1453',
            'end_date' => '1453',
            'is_primary' => true,
        ]);

        EntityLocation::query()->create([
            'entity_id' => $source->entity_id,
            'location_name' => 'Source Place',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [12.4964, 41.9028],
            ],
        ]);

        EntityLocation::query()->create([
            'entity_id' => $target->entity_id,
            'location_name' => 'Constantinople',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [28.9784, 41.0082],
            ],
        ]);

        EntityRelationship::query()->create([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'located_at',
            'start_year' => 1453,
            'end_year' => 1453,
            'created_by' => 'test',
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $this->assertDatabaseHas('geometry_periods', [
            'entity_id' => $source->entity_id,
            'period_type' => 'presence',
            'relationship_id' => $relationshipId,
            'start_year' => 1453,
            'end_year' => 1453,
            'provenance_mode' => 'derived',
            'created_by' => 'backfill:entity-model-v2',
        ]);
    }

    public function test_backfill_command_uses_counterparty_geometry_for_derived_presence_periods(): void
    {
        $source = Entity::factory()->create();
        $target = Entity::factory()->create();
        $relationshipId = (string) Str::uuid();

        EntityTemporalRange::query()->create([
            'entity_id' => $source->entity_id,
            'range_type' => 'primary',
            'start_date' => '-0100',
            'end_date' => '-0090',
            'is_primary' => true,
        ]);

        EntityLocation::query()->create([
            'entity_id' => $source->entity_id,
            'location_name' => 'Source City',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [10.0, 45.0],
            ],
        ]);

        EntityLocation::query()->create([
            'entity_id' => $target->entity_id,
            'location_name' => 'Target City',
            'is_primary' => true,
            'geom' => [
                'type' => 'Point',
                'coordinates' => [30.0, 50.0],
            ],
        ]);

        EntityRelationship::query()->create([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'contributed_to',
            'created_by' => 'test',
        ]);

        $this->artisan('entity-model-v2:backfill')->assertExitCode(0);

        $period = GeometryPeriod::query()
            ->where('entity_id', $source->entity_id)
            ->where('relationship_id', $relationshipId)
            ->firstOrFail();

        $this->assertSame('Point', $period->geom['type'] ?? null);
        $this->assertEquals([30.0, 50.0], $period->geom['coordinates'] ?? null);
    }
}
