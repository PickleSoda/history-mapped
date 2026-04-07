<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class BackfillEntityModelV2CommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_backfill_command_migrates_core_legacy_entity_fields(): void
    {
        $entity = Entity::factory()->create([
            'alternative_names' => ['Imperium Romanum', 'Res Publica Romana'],
            'tags' => ['rome', 'republic'],
            'temporal_start' => '-0509',
            'temporal_end' => '-0027',
            'temporal_start_year' => -509,
            'temporal_end_year' => -27,
            'location_name' => 'Rome',
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
        $entity = Entity::factory()->create([
            'alternative_names' => ['Roma'],
            'tags' => ['rome'],
            'temporal_start' => '-0753',
            'temporal_end' => null,
            'temporal_start_year' => -753,
            'location_name' => 'Rome',
        ]);

        $this->artisan('entity-model-v2:backfill --dry-run')
            ->expectsOutputToContain('[DRY-RUN] Entity Model V2 backfill summary')
            ->assertExitCode(0);

        $this->assertDatabaseMissing('entity_aliases', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_tags', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_temporal_ranges', ['entity_id' => $entity->entity_id]);
        $this->assertDatabaseMissing('entity_locations', ['entity_id' => $entity->entity_id]);
    }
}
