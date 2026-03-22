<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotBuilderTest extends TestCase
{
    use RefreshDatabase;

    public function test_at_year_returns_snapshots_covering_year(): void
    {
        $entity = Entity::factory()->create();

        $early = GeometrySnapshot::factory()->forEntity($entity)->forYears(-27, 14)->create();
        $middle = GeometrySnapshot::factory()->forEntity($entity)->forYears(14, 117)->create();
        GeometrySnapshot::factory()->forEntity($entity)->forYears(200, 300)->create();

        $results = GeometrySnapshot::query()
            ->forEntity($entity->entity_id)
            ->atYear(14)
            ->orderChronologically()
            ->get();

        $this->assertCount(2, $results);
        $this->assertSame([$early->snapshot_id, $middle->snapshot_id], $results->pluck('snapshot_id')->all());
    }

    public function test_in_bbox_filters_territory_snapshots(): void
    {
        $entity = Entity::factory()->create();

        $inside = GeometrySnapshot::factory()
            ->forEntity($entity)
            ->withTerritoryGeometry([
                'type' => 'Polygon',
                'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
            ])
            ->create();

        $outside = GeometrySnapshot::factory()
            ->forEntity($entity)
            ->withTerritoryGeometry([
                'type' => 'Polygon',
                'coordinates' => [[[-70.0, 10.0], [-69.0, 10.0], [-69.0, 11.0], [-70.0, 11.0], [-70.0, 10.0]]],
            ])
            ->create();

        $results = GeometrySnapshot::query()
            ->inBbox(0, 30, 30, 50)
            ->get();

        $this->assertTrue($results->contains('snapshot_id', $inside->snapshot_id));
        $this->assertFalse($results->contains('snapshot_id', $outside->snapshot_id));
    }

    public function test_with_geojson_selects_virtual_geojson_columns(): void
    {
        $entity = Entity::factory()->create();

        $snapshot = GeometrySnapshot::factory()
            ->forEntity($entity)
            ->withTerritoryGeometry()
            ->create();

        $result = GeometrySnapshot::query()
            ->whereKey($snapshot->snapshot_id)
            ->withGeoJson()
            ->firstOrFail();

        $attributes = $result->getAttributes();

        $this->assertArrayHasKey('geom_geojson', $attributes);
        $this->assertArrayHasKey('territory_geom_geojson', $attributes);
        $this->assertNotNull($attributes['territory_geom_geojson']);
    }
}
