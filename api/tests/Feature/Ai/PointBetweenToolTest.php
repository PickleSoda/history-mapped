<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\PointBetween;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Services\Geo\SphericalGeometry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Ai\Tools\Request;
use Tests\TestCase;

class PointBetweenToolTest extends TestCase
{
    use RefreshDatabase;

    /** @return array<string, mixed> */
    private function between(array $args): array
    {
        return json_decode(app(PointBetween::class)->handle(new Request($args)), true);
    }

    public function test_midway_between_two_coordinates(): void
    {
        $data = $this->between(['a_lon' => 10, 'a_lat' => 0, 'b_lon' => 10, 'b_lat' => 20]);

        $this->assertEqualsWithDelta(10.0, $data['lon'], 1e-5);
        $this->assertEqualsWithDelta(10.0, $data['lat'], 1e-5);
        $this->assertEqualsWithDelta(2223.9, $data['distance_a_b_km'], 0.1);
        $this->assertEqualsWithDelta($data['distance_a_b_km'] / 2, $data['from_a_km'], 0.1);
        $this->assertSame(0.0, (float) $data['bearing_a_to_b']);
        $this->assertStringStartsWith('Midway from (10.00000, 0.00000) toward (10.00000, 20.00000)', $data['explanation']);
    }

    public function test_fraction_toward_an_entity_anchor(): void
    {
        $paris = Entity::factory()->create(['name' => 'Paris', 'entity_type' => EntityType::City->value, 'entity_group' => 'PLACE']);
        EntityLocation::create([
            'entity_id' => $paris->entity_id,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [2.3522, 48.8566]],
        ]);

        $data = $this->between(['a_lon' => 12.4964, 'a_lat' => 41.9028, 'b_entity_id' => $paris->entity_id, 'fraction' => 0.25]);

        $total = SphericalGeometry::distanceKm(12.4964, 41.9028, 2.3522, 48.8566);
        $this->assertEqualsWithDelta($total / 4, SphericalGeometry::distanceKm(12.4964, 41.9028, $data['lon'], $data['lat']), 0.01);
        $this->assertStringStartsWith('25% of the way from (12.49640, 41.90280) toward Paris', $data['explanation']);
    }

    public function test_rejects_a_missing_anchor_or_bad_fraction(): void
    {
        $this->assertStringContainsString('anchor B', $this->between(['a_lon' => 1, 'a_lat' => 1])['error']);
        $this->assertStringContainsString('fraction', $this->between(['a_lon' => 1, 'a_lat' => 1, 'b_lon' => 2, 'b_lat' => 2, 'fraction' => 1.5])['error']);
    }
}
