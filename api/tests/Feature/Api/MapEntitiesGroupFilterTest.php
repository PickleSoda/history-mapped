<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesGroupFilterTest extends TestCase
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

    public function test_group_filter_excludes_other_groups(): void
    {
        $polity = Entity::factory()->verified()->create(['entity_group' => 'POLITY']);
        $place = Entity::factory()->verified()->create(['entity_group' => 'PLACE']);
        $this->setGeometryPeriod($polity, 900, 1100);
        $this->setGeometryPeriod($place, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
            'group' => 'POLITY',
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($polity->entity_id, $ids);
        $this->assertNotContains($place->entity_id, $ids);
    }

    public function test_groups_filter_includes_only_selected_groups(): void
    {
        $polity = Entity::factory()->verified()->create(['entity_group' => 'POLITY']);
        $event = Entity::factory()->verified()->create(['entity_group' => 'EVENT']);
        $place = Entity::factory()->verified()->create(['entity_group' => 'PLACE']);
        $this->setGeometryPeriod($polity, 900, 1100);
        $this->setGeometryPeriod($event, 900, 1100);
        $this->setGeometryPeriod($place, 900, 1100);

        $response = $this->getJson(route('api.v1.entities.map', [
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
            'year' => 1000,
            'groups' => ['POLITY', 'EVENT'],
        ]));

        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($polity->entity_id, $ids);
        $this->assertContains($event->entity_id, $ids);
        $this->assertNotContains($place->entity_id, $ids);
    }
}
