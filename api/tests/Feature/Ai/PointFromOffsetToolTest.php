<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\PointFromOffset;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Services\Geo\SphericalGeometry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Ai\Tools\Request;
use Tests\TestCase;

class PointFromOffsetToolTest extends TestCase
{
    use RefreshDatabase;

    /** @return array<string, mixed> */
    private function offset(array $args): array
    {
        return json_decode(app(PointFromOffset::class)->handle(new Request($args)), true);
    }

    public function test_moves_north_from_coordinates(): void
    {
        $data = $this->offset(['from_lon' => 12.4964, 'from_lat' => 41.9028, 'distance' => 111.195, 'direction' => 'north']);

        $this->assertEqualsWithDelta(42.9028, $data['lat'], 1e-3);
        $this->assertEqualsWithDelta(12.4964, $data['lon'], 1e-4);
        $this->assertSame(0.0, (float) $data['bearing']);
        $this->assertStringContainsString('N (0°) of (12.49640, 41.90280)', $data['explanation']);
        $this->assertStringContainsString('set_entity_location', $data['next']);
    }

    public function test_anchors_on_an_entity_and_converts_units(): void
    {
        $rome = Entity::factory()->create(['name' => 'Rome', 'entity_type' => EntityType::City->value, 'entity_group' => 'PLACE']);
        EntityLocation::create([
            'entity_id' => $rome->entity_id,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [12.4964, 41.9028]],
        ]);

        $data = $this->offset(['from_entity_id' => 'Rome', 'distance' => 10, 'unit' => 'roman_mile', 'direction' => 'NNE']);

        $this->assertEqualsWithDelta(14.8, $data['distance_km'], 1e-9);
        $this->assertEqualsWithDelta(14.8, SphericalGeometry::distanceKm(12.4964, 41.9028, $data['lon'], $data['lat']), 0.01);
        $this->assertStringContainsString('10 roman_mile (14.8 km) NNE (22.5°) of Rome', $data['explanation']);
    }

    public function test_accepts_a_bearing_in_degrees(): void
    {
        $data = $this->offset(['from_lon' => 0, 'from_lat' => 0, 'distance' => 50, 'direction' => '90']);

        $this->assertEqualsWithDelta(0.0, $data['lat'], 1e-6);
        $this->assertGreaterThan(0.44, $data['lon']);
    }

    public function test_explains_bad_input(): void
    {
        $this->assertStringContainsString('direction', $this->offset(['from_lon' => 0, 'from_lat' => 0, 'distance' => 5, 'direction' => 'upstream'])['error']);
        $this->assertStringContainsString('positive', $this->offset(['from_lon' => 0, 'from_lat' => 0, 'distance' => -5, 'direction' => 'N'])['error']);
        $this->assertStringContainsString('out of range', $this->offset(['from_lon' => 41.9, 'from_lat' => 112.5, 'distance' => 5, 'direction' => 'N'])['error']);
        $this->assertStringContainsString('find_place', $this->offset(['distance' => 5, 'direction' => 'N'])['error']);
        $this->assertStringContainsString('find_place', $this->offset(['from_entity_id' => 'Nowhere', 'distance' => 5, 'direction' => 'N'])['error']);
    }
}
