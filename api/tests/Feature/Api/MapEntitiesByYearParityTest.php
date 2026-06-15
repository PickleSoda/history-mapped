<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * Parity fixes for the live /entities/map/year endpoint, bringing it in line
 * with /entities/map: MQ-16 (DISTINCT ON dedup), MQ-15 (display_priority /
 * impact_score NULLS LAST), MQ-13 (group filter).
 */
class MapEntitiesByYearParityTest extends TestCase
{
    use RefreshDatabase;

    private function addTerritoryPeriod(Entity $entity, int $startYear, int $endYear): void
    {
        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                territory_geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), ?, 'territory', ?, ?,
                ST_SetSRID(ST_GeomFromText('POLYGON((10 40, 11 40, 11 41, 10 41, 10 40))'), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [$entity->entity_id, $startYear, $endYear],
        );
    }

    // ── MQ-16: duplicate features per entity ────────────────────────────────

    public function test_overlapping_periods_yield_one_feature_per_entity(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->addTerritoryPeriod($entity, 900, 1100);
        $this->addTerritoryPeriod($entity, 950, 1050); // both cover year 1000

        $response = $this->getJson(route('api.v1.entities.map.year', ['year' => 1000]));

        $response->assertOk();
        $features = collect($response->json('features'))->where('id', $entity->entity_id);
        $this->assertCount(1, $features, 'an entity with overlapping periods should appear once');
    }

    public function test_all_periods_opt_out_returns_every_period(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->addTerritoryPeriod($entity, 900, 1100);
        $this->addTerritoryPeriod($entity, 950, 1050);

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
            'all_periods' => 1,
        ]));

        $response->assertOk();
        $features = collect($response->json('features'))->where('id', $entity->entity_id);
        $this->assertCount(2, $features, 'all_periods=1 should return every covering period');
    }

    // ── MQ-15: curation ordering (NULLS LAST) ───────────────────────────────

    public function test_prioritized_entity_outranks_null_priority_under_limit(): void
    {
        $curated = Entity::factory()->verified()->create();
        $uncurated = Entity::factory()->verified()->create();
        DB::table('entities')->where('entity_id', $curated->entity_id)->update(['display_priority' => 10]);
        DB::table('entities')->where('entity_id', $uncurated->entity_id)->update(['display_priority' => null]);
        $this->addTerritoryPeriod($curated, 900, 1100);
        $this->addTerritoryPeriod($uncurated, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
            'limit' => 1,
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertSame([$curated->entity_id], $ids, 'the curated (non-null priority) entity must win the single slot');
    }

    // ── MQ-13: group filter ─────────────────────────────────────────────────

    public function test_group_filter_excludes_other_groups(): void
    {
        $polity = Entity::factory()->verified()->create(['entity_group' => 'POLITY']);
        $place = Entity::factory()->verified()->create(['entity_group' => 'PLACE']);
        $this->addTerritoryPeriod($polity, 900, 1100);
        $this->addTerritoryPeriod($place, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map.year', [
            'year' => 1000,
            'group' => 'POLITY',
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($polity->entity_id, $ids);
        $this->assertNotContains($place->entity_id, $ids);
    }
}
