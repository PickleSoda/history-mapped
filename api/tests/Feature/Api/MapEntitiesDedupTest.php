<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesDedupTest extends TestCase
{
    use RefreshDatabase;

    private function setGeometryPeriod(Entity $entity, int $startYear, int $endYear): void
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

    private function bbox(): array
    {
        return [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
        ];
    }

    public function test_one_feature_per_entity_with_multiple_periods(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 900, 1100); // covers 1000
        $this->setGeometryPeriod($entity, 950, 1050); // also covers 1000

        $response = $this->getJson(route('api.v1.entities.map', $this->bbox()));
        $response->assertOk();

        $ids = collect($response->json('features'))->pluck('id');
        $this->assertSame(1, $ids->filter(fn ($id) => $id === $entity->entity_id)->count());
    }

    public function test_all_periods_opt_out_returns_every_period(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->setGeometryPeriod($entity, 900, 1100);
        $this->setGeometryPeriod($entity, 950, 1050);

        $response = $this->getJson(route('api.v1.entities.map', [...$this->bbox(), 'all_periods' => 1]));
        $response->assertOk();

        $ids = collect($response->json('features'))->pluck('id');
        $this->assertSame(2, $ids->filter(fn ($id) => $id === $entity->entity_id)->count());
    }

    public function test_display_priority_outranks_null_under_limit(): void
    {
        $curated = Entity::factory()->verified()->create(['display_priority' => 100]);
        $uncurated = Entity::factory()->verified()->create(['display_priority' => null]);
        $this->setGeometryPeriod($curated, 900, 1100);
        $this->setGeometryPeriod($uncurated, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [...$this->bbox(), 'limit' => 1]));
        $response->assertOk();

        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($curated->entity_id, $ids);
        $this->assertNotContains($uncurated->entity_id, $ids);
    }
}
