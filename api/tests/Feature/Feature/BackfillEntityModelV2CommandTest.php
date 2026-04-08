<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
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
}
