<?php

namespace App\Ai\Tools;

use App\Ai\Tools\Concerns\ComputesPlacement;
use App\Services\Geo\PlaceFinder;
use App\Services\Geo\SphericalGeometry;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use Stringable;

class PointBetween extends AgentTool
{
    use ComputesPlacement;

    public function __construct(
        private PlaceFinder $places,
    ) {}

    public static function name(): string
    {
        return 'point_between';
    }

    public function description(): string
    {
        return 'Compute a point on the straight (great-circle) line between two anchors — for "midway between A and B", "between A and B, closer to A" (fraction 0.3), "a third of the way from A to B" (fraction 0.333). '
            .'Give each anchor as lon + lat (e.g. from find_place) or as an entity. Also returns the A–B distance and direction.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'a_lon' => $schema->number()->description('Anchor A longitude (east-west).'),
            'a_lat' => $schema->number()->description('Anchor A latitude (north-south).'),
            'a_entity_id' => $schema->string()->description('Instead of a_lon/a_lat: anchor A\'s entity UUID or exact name.'),
            'b_lon' => $schema->number()->description('Anchor B longitude (east-west).'),
            'b_lat' => $schema->number()->description('Anchor B latitude (north-south).'),
            'b_entity_id' => $schema->string()->description('Instead of b_lon/b_lat: anchor B\'s entity UUID or exact name.'),
            'fraction' => $schema->number()->description('How far from A toward B, 0..1. Default 0.5 (midway); 0.25 = a quarter of the way from A; "closer to A" ≈ 0.3, "closer to B" ≈ 0.7.'),
        ];
    }

    /** Read-only: returns the computed point, no proposal staged. */
    public function handle(Request $request): Stringable|string
    {
        $a = $this->anchor($request, 'a_', 'anchor A');
        if (isset($a['error'])) {
            return $this->failure($a['error']);
        }
        $b = $this->anchor($request, 'b_', 'anchor B');
        if (isset($b['error'])) {
            return $this->failure($b['error']);
        }

        $fraction = $request['fraction'] ?? 0.5;
        if (! is_numeric($fraction) || (float) $fraction < 0 || (float) $fraction > 1) {
            return $this->failure('fraction must be between 0 (at A) and 1 (at B).');
        }
        $fraction = (float) $fraction;

        $distance = SphericalGeometry::distanceKm($a['lon'], $a['lat'], $b['lon'], $b['lat']);
        $bearing = SphericalGeometry::initialBearing($a['lon'], $a['lat'], $b['lon'], $b['lat']);
        $point = SphericalGeometry::intermediate($a['lon'], $a['lat'], $b['lon'], $b['lat'], $fraction);

        $where = $fraction === 0.5
            ? 'Midway'
            : sprintf('%s%% of the way', rtrim(rtrim(number_format($fraction * 100, 1, '.', ''), '0'), '.'));

        return $this->placed(
            $point['lon'],
            $point['lat'],
            sprintf(
                '%s from %s toward %s (%s km apart, %s) → %s',
                $where,
                $a['label'],
                $b['label'],
                number_format($distance, 1, '.', ''),
                SphericalGeometry::compassLabel($bearing),
                self::coords($point['lon'], $point['lat']),
            ),
            [
                'distance_a_b_km' => round($distance, 1),
                'from_a_km' => round($distance * $fraction, 1),
                'bearing_a_to_b' => round($bearing, 1),
            ],
            array_values(array_filter([$a['warning'] ?? null, $b['warning'] ?? null])),
        );
    }
}
