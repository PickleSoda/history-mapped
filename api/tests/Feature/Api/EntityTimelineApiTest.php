<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class EntityTimelineApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_timeline_endpoint_returns_relationship_denormalized_fields(): void
    {
        $caesar = Entity::factory()->create(['name' => 'Julius Caesar']);
        $alesia = Entity::factory()->create(['name' => 'Siege of Alesia']);

        $relationshipId = Str::uuid()->toString();

        DB::table('relationships')->insert([
            'relationship_id' => $relationshipId,
            'source_entity_id' => $caesar->entity_id,
            'target_entity_id' => $alesia->entity_id,
            'relationship_type' => 'victorious_at',
            'temporal_start' => '-0052',
            'temporal_end' => '-0052',
            'start_year' => -52,
            'end_year' => -52,
            'created_by' => 'test',
            'created_at' => now(),
        ]);

        $periodId = Str::uuid()->toString();

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, relationship_id, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'presence', -52, -52,
                ST_SetSRID(ST_MakePoint(4.5, 47.5), 4326), 'derived', ?, 'test', NOW(), NOW()
            )",
            [$periodId, $caesar->entity_id, $relationshipId],
        );

        $this->artisan('timeline:rebuild', ['entity_id' => $caesar->entity_id])->assertExitCode(0);

        $this->getJson(route('api.v1.entities.timeline.index', $caesar->entity_id))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.relationship_type', 'victorious_at')
            ->assertJsonPath('data.0.related_entity_id', $alesia->entity_id)
            ->assertJsonPath('data.0.related_entity_name', 'Siege of Alesia')
            ->assertJsonPath('data.0.start_year', -52)
            ->assertJsonPath('data.0.end_year', -52)
            ->assertJsonPath('data.0.source_table', 'geometry_periods')
            ->assertJsonPath('data.0.source_id', $periodId);
    }
}
