<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\NearestCoast;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as HttpRequest;
use Illuminate\Support\Facades\Http;
use Laravel\Ai\Tools\Request;
use Tests\TestCase;

class NearestCoastToolTest extends TestCase
{
    use RefreshDatabase;

    /**
     * An east-running coastline along latitude 41.7 (land to its left, i.e.
     * north), split by a clipping gap that must not become a fake segment.
     */
    private function fakeCoast(): void
    {
        Http::fake([
            'overpass-api.de/*' => Http::response(['elements' => [[
                'type' => 'way',
                'id' => 1,
                'geometry' => [
                    ['lon' => 12.0, 'lat' => 41.7],
                    ['lon' => 12.6, 'lat' => 41.7],
                    null,
                    ['lon' => 14.0, 'lat' => 40.0],
                    ['lon' => 15.0, 'lat' => 40.0],
                ],
            ]]]),
        ]);
    }

    /** @return array<string, mixed> */
    private function coast(array $args): array
    {
        return json_decode(app(NearestCoast::class)->handle(new Request($args)), true);
    }

    public function test_finds_the_shore_point(): void
    {
        $this->fakeCoast();

        $data = $this->coast(['lon' => 12.3, 'lat' => 41.9]);

        $this->assertEqualsWithDelta(12.3, $data['lon'], 1e-4);
        $this->assertEqualsWithDelta(41.7, $data['lat'], 1e-4);
        $this->assertSame($data['lon'], $data['shore_lon']);
        $this->assertEqualsWithDelta(22.2, $data['distance_to_shore_km'], 0.1);
        // Land lies left of an east-running coast: inland is (about) due north.
        $this->assertLessThan(0.5, min($data['inland_bearing'], 360.0 - $data['inland_bearing']));
        $this->assertStringStartsWith('Shore point 22.2 km S of (12.30000, 41.90000)', $data['explanation']);
        $this->assertStringContainsString('Modern coastline', implode(' ', $data['warnings']));

        // One box ~50 km around the anchor, used to filter and to clip.
        Http::assertSent(function (HttpRequest $request): bool {
            return preg_match('/way\["natural"="coastline"\]\((41\.4[0-9]+),[0-9.]+,(42\.3[0-9]+),[0-9.]+\);out geom\(\1,[0-9.]+,\2,[0-9.]+\);/', urldecode($request->body())) === 1;
        });
    }

    public function test_does_not_bridge_a_clipping_gap(): void
    {
        $this->fakeCoast();

        // A segment invented across the gap would pass ~30 km away; the real
        // nearest shore is the end of the first piece, ~93 km away.
        $data = $this->coast(['lon' => 13.5, 'lat' => 41.2, 'max_km' => 200]);

        $this->assertEqualsWithDelta(12.6, $data['shore_lon'], 1e-4);
        $this->assertEqualsWithDelta(41.7, $data['shore_lat'], 1e-4);
        $this->assertGreaterThan(80, $data['distance_to_shore_km']);
    }

    public function test_offsets_inland_or_out_to_sea(): void
    {
        $this->fakeCoast();

        $inland = $this->coast(['lon' => 12.3, 'lat' => 41.9, 'offset_km' => 2]);
        $this->assertGreaterThan(41.7, $inland['lat']);
        $this->assertStringContainsString('inland', $inland['explanation']);

        $sea = $this->coast(['lon' => 12.3, 'lat' => 41.9, 'offset_km' => -2]);
        $this->assertLessThan(41.7, $sea['lat']);
        $this->assertStringContainsString('out to sea', $sea['explanation']);
    }

    public function test_reports_no_coast_in_range(): void
    {
        Http::fake(['overpass-api.de/*' => Http::response(['elements' => []])]);

        $this->assertStringContainsString('No sea coast within 50 km', $this->coast(['lon' => 10, 'lat' => 50])['error']);
    }

    public function test_reports_an_unavailable_service(): void
    {
        Http::fake(['overpass-api.de/*' => Http::response('rate limited', 429)]);

        $this->assertStringContainsString('unavailable', $this->coast(['lon' => 12.3, 'lat' => 41.9])['error']);
    }

    public function test_rejects_a_large_offset(): void
    {
        $this->assertStringContainsString('offset_km', $this->coast(['lon' => 12.3, 'lat' => 41.9, 'offset_km' => 500])['error']);
    }
}
