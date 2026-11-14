<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\EntityTimelineEntry;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

class EntityDetailGeometrySnapshotsCountTest extends TestCase
{
    use RefreshDatabase;

    public function test_entity_detail_exposes_geometry_period_and_timeline_counts(): void
    {
        $entity = Entity::factory()->create();

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => -200,
            'end_year' => -150,
            'provenance_mode' => 'manual',
            'created_by' => 'test',
            'territory_geom' => [
                'type' => 'Polygon',
                'coordinates' => [[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]],
            ],
        ]);

        EntityTimelineEntry::query()->create([
            'timeline_entry_id' => Str::uuid()->toString(),
            'entity_id' => $entity->entity_id,
            'entry_kind' => 'territory_period',
            'start_year' => -200,
            'end_year' => -150,
            'title' => 'Territory period',
            'source_table' => 'geometry_periods',
            'source_id' => Str::uuid()->toString(),
        ]);

        $response = $this->getJson(route('api.v1.entities.show', $entity->entity_id));

        $response->assertOk()
            ->assertJsonPath('data.geometry_periods_count', 1);

        $this->assertGreaterThanOrEqual(1, (int) $response->json('data.timeline_entries_count'));
    }

    public function test_entity_detail_leaves_out_internal_attributes(): void
    {
        $entity = Entity::factory()->create(['attributes' => [
            'capital' => 'Persepolis',
            'confidence_notes' => 'Dates follow Briant.',
            'validation_flags' => ['no_wikidata_match'],
            '_rejected_wikidata_id' => 'Q1',
            '_backfill_runs' => [['at' => '2026-11-01']],
        ]]);

        $this->getJson(route('api.v1.entities.show', $entity->entity_id))
            ->assertOk()
            ->assertJsonPath('data.attributes', [
                'capital' => 'Persepolis',
                'confidence_notes' => 'Dates follow Briant.',
            ])
            ->assertJsonPath('data.confidence_notes', 'Dates follow Briant.')
            ->assertJsonMissingPath('data.validation_flags');
    }
}
