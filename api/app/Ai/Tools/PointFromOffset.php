<?php

namespace App\Ai\Tools;

use App\Ai\Tools\Concerns\ComputesPlacement;
use App\Services\Geo\PlaceFinder;
use App\Services\Geo\SphericalGeometry;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use Stringable;

class PointFromOffset extends AgentTool
{
    use ComputesPlacement;

    /** Kilometres per unit. The Roman mile is the usual 1,000 paces. */
    private const UNITS = ['km' => 1.0, 'm' => 0.001, 'mi' => 1.609344, 'nmi' => 1.852, 'roman_mile' => 1.48];

    private const MAX_KM = 20000.0;

    public function __construct(
        private PlaceFinder $places,
    ) {}

    public static function name(): string
    {
        return 'point_from_offset';
    }

    public function description(): string
    {
        return 'Compute the point a given distance and direction from an anchor — for "X km north of Y", "30 miles south-east of Y", "a day\'s march (~30 km) west of Y". '
            .'Give the anchor as from_lon + from_lat (e.g. from find_place) or from_entity_id. Returns lon/lat for set_entity_location.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'from_lon' => $schema->number()->description('Anchor longitude (east-west, -180..180).'),
            'from_lat' => $schema->number()->description('Anchor latitude (north-south, -90..90).'),
            'from_entity_id' => $schema->string()->description('Instead of from_lon/from_lat: the anchor entity\'s UUID or exact name.'),
            'distance' => $schema->number()->description('How far from the anchor, in `unit` (default km).')->required(),
            'unit' => $schema->string()->enum(array_keys(self::UNITS))->description('km (default), m, mi (statute miles), nmi (nautical miles) or roman_mile (1.48 km).'),
            'direction' => $schema->string()->description('Compass direction from the anchor: N, NNE, NE, E, SE, S, SW, W, NW…, words like "north-east" or "due west", or a bearing in degrees ("45" = north-east, "90" = east).')->required(),
        ];
    }

    /** Read-only: returns the computed point, no proposal staged. */
    public function handle(Request $request): Stringable|string
    {
        $anchor = $this->anchor($request, 'from_', 'the anchor');
        if (isset($anchor['error'])) {
            return $this->failure($anchor['error']);
        }

        $unit = array_key_exists((string) ($request['unit'] ?? ''), self::UNITS) ? (string) $request['unit'] : 'km';
        $distance = $request['distance'] ?? null;
        if (! is_numeric($distance) || (float) $distance <= 0) {
            return $this->failure('distance must be a positive number.');
        }
        $km = (float) $distance * self::UNITS[$unit];
        if ($km > self::MAX_KM) {
            return $this->failure('distance is larger than half the Earth — check the unit.');
        }

        $direction = $request['direction'] ?? null;
        $bearing = is_string($direction) || is_int($direction) || is_float($direction)
            ? SphericalGeometry::parseDirection($direction)
            : null;
        if ($bearing === null) {
            return $this->failure('Unrecognised direction. Use a compass point (N, NE, SSW…), words like "north-east", or a bearing in degrees (0 = north, 90 = east).');
        }

        $point = SphericalGeometry::destination($anchor['lon'], $anchor['lat'], $km, $bearing);
        $howFar = $unit === 'km'
            ? self::number($km).' km'
            : self::number((float) $distance)." {$unit} (".self::number($km).' km)';

        return $this->placed(
            $point['lon'],
            $point['lat'],
            sprintf(
                '%s %s (%s°) of %s → %s',
                $howFar,
                SphericalGeometry::compassLabel($bearing),
                self::number($bearing),
                $anchor['label'],
                self::coords($point['lon'], $point['lat']),
            ),
            ['distance_km' => round($km, 3), 'bearing' => round($bearing, 2)],
            isset($anchor['warning']) ? [$anchor['warning']] : [],
        );
    }

    private static function number(float $value): string
    {
        return rtrim(rtrim(number_format($value, 2, '.', ''), '0'), '.');
    }
}
