<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapEntitiesTemporalIndexTest extends TestCase
{
    use RefreshDatabase;

    /**
     * A non-event entity, so the plain int4range temporal semantics are exercised
     * (EVENTs are decade-padded — see test_event_period_is_decade_sticky). The
     * factory picks a random type, which would otherwise make these tests flaky.
     */
    private function nonEvent(): Entity
    {
        return Entity::factory()->verified()->create([
            'entity_type' => EntityType::PoliticalEntity->value,
            'entity_group' => EntityGroup::Polity->value,
        ]);
    }

    private function setGeometryPeriod(Entity $entity, int $startYear, ?int $endYear): void
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

    private function bbox(array $extra): array
    {
        return array_merge([
            'bbox_min_lng' => 0,
            'bbox_min_lat' => 30,
            'bbox_max_lng' => 30,
            'bbox_max_lat' => 50,
        ], $extra);
    }

    public function test_open_ended_period_matches_year_after_start(): void
    {
        $entity = $this->nonEvent();
        $this->setGeometryPeriod($entity, 1000, null); // ongoing

        $response = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1500])));
        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($entity->entity_id, $ids);
    }

    public function test_end_year_is_inclusive(): void
    {
        $entity = $this->nonEvent();
        $this->setGeometryPeriod($entity, 900, 1100);

        $atEnd = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1100])));
        $this->assertContains($entity->entity_id, collect($atEnd->json('features'))->pluck('id')->all());

        $afterEnd = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => 1101])));
        $this->assertNotContains($entity->entity_id, collect($afterEnd->json('features'))->pluck('id')->all());
    }

    public function test_event_period_is_decade_sticky(): void
    {
        // A momentary event stored as a point (1917) surfaces within ±10 years on
        // the continuous timeline, but not a whole century away.
        $event = Entity::factory()->verified()->create([
            'entity_type' => EntityType::EventBattle->value,
            'entity_group' => EntityGroup::Event->value,
        ]);
        $this->setGeometryPeriod($event, 1917, 1917);

        foreach ([1917, 1908, 1927] as $within) {
            $res = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => $within])));
            $this->assertContains($event->entity_id, collect($res->json('features'))->pluck('id')->all(), "expected event at year {$within}");
        }
        foreach ([1928, 1850, 2000] as $beyond) {
            $res = $this->getJson(route('api.v1.entities.map', $this->bbox(['year' => $beyond])));
            $this->assertNotContains($event->entity_id, collect($res->json('features'))->pluck('id')->all(), "event should not appear at year {$beyond}");
        }
    }

    public function test_range_overlap(): void
    {
        $inRange = $this->nonEvent();
        $this->setGeometryPeriod($inRange, 1500, 1600);

        $outRange = $this->nonEvent();
        $this->setGeometryPeriod($outRange, 1000, 1100);

        $response = $this->getJson(route('api.v1.entities.map', $this->bbox([
            'temporal_start' => 1550,
            'temporal_end' => 1700,
        ])));
        $response->assertOk();
        $ids = collect($response->json('features'))->pluck('id')->all();
        $this->assertContains($inRange->entity_id, $ids);
        $this->assertNotContains($outRange->entity_id, $ids);
    }
}
