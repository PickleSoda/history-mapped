<?php

namespace App\Ai\Tools;

use App\Ai\Tools\Concerns\ComputesPlacement;
use App\Services\Geo\CoastlineLookup;
use App\Services\Geo\PlaceFinder;
use App\Services\Geo\SphericalGeometry;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use RuntimeException;
use Stringable;

class NearestCoast extends AgentTool
{
    use ComputesPlacement;

    private const DEFAULT_MAX_KM = 50.0;

    private const MAX_MAX_KM = 200.0;

    private const MAX_OFFSET_KM = 50.0;

    public function __construct(
        private PlaceFinder $places,
        private CoastlineLookup $coast,
    ) {}

    public static function name(): string
    {
        return 'nearest_coast';
    }

    public function description(): string
    {
        return 'Find the nearest point on the sea coast to an anchor — for "on the shore near X", "a harbour by X", "off the coast of X". '
            .'Give the anchor as lon + lat (e.g. from find_place) or entity_id. offset_km moves the result inland (positive) or out to sea (negative) from the shore. '
            .'Uses today\'s OpenStreetMap coastline, so ancient shores may differ.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'lon' => $schema->number()->description('Anchor longitude (east-west).'),
            'lat' => $schema->number()->description('Anchor latitude (north-south).'),
            'entity_id' => $schema->string()->description('Instead of lon/lat: the anchor entity\'s UUID or exact name.'),
            'max_km' => $schema->number()->description('Search radius around the anchor, km. Default 50, at most 200.'),
            'offset_km' => $schema->number()->description('Optional: move this far from the shore point — positive = inland, negative = out to sea. Default 0 (on the shoreline).'),
        ];
    }

    /** Read-only: returns the shore point, no proposal staged. */
    public function handle(Request $request): Stringable|string
    {
        $anchor = $this->anchor($request, '', 'the anchor');
        if (isset($anchor['error'])) {
            return $this->failure($anchor['error']);
        }

        $maxKm = is_numeric($request['max_km'] ?? null) ? (float) $request['max_km'] : self::DEFAULT_MAX_KM;
        $maxKm = max(1.0, min(self::MAX_MAX_KM, $maxKm));
        $offset = is_numeric($request['offset_km'] ?? null) ? (float) $request['offset_km'] : 0.0;
        if (abs($offset) > self::MAX_OFFSET_KM) {
            return $this->failure('offset_km must be between -50 and 50.');
        }

        try {
            $shore = $this->coast->nearest($anchor['lon'], $anchor['lat'], $maxKm);
        } catch (RuntimeException $e) {
            report($e);

            return $this->failure('The coastline service is unavailable right now. Try again shortly, or estimate the spot with point_from_offset.');
        }

        if ($shore === null) {
            return $this->failure(sprintf(
                'No sea coast within %s km of %s. The anchor may be inland — raise max_km (up to 200) or check the anchor. Lake and river shores are not covered.',
                number_format($maxKm, 0, '.', ''),
                $anchor['label'],
            ));
        }

        $toShore = SphericalGeometry::initialBearing($anchor['lon'], $anchor['lat'], $shore['lon'], $shore['lat']);
        $explanation = sprintf(
            'Shore point %s km %s of %s → %s',
            number_format($shore['distance_km'], 1, '.', ''),
            SphericalGeometry::compassLabel($toShore),
            $anchor['label'],
            self::coords($shore['lon'], $shore['lat']),
        );

        $point = ['lon' => $shore['lon'], 'lat' => $shore['lat']];
        if ($offset !== 0.0) {
            $bearing = $offset > 0 ? $shore['inland_bearing'] : SphericalGeometry::normalizeBearing($shore['inland_bearing'] + 180.0);
            $point = SphericalGeometry::destination($shore['lon'], $shore['lat'], abs($offset), $bearing);
            $explanation .= sprintf(
                ', then %s km %s → %s',
                number_format(abs($offset), 1, '.', ''),
                $offset > 0 ? 'inland' : 'out to sea',
                self::coords($point['lon'], $point['lat']),
            );
        }

        return $this->placed(
            $point['lon'],
            $point['lat'],
            $explanation,
            [
                'shore_lon' => round($shore['lon'], 5),
                'shore_lat' => round($shore['lat'], 5),
                'distance_to_shore_km' => round($shore['distance_km'], 2),
                'inland_bearing' => round($shore['inland_bearing'], 1),
            ],
            array_values(array_filter([
                $anchor['warning'] ?? null,
                'Modern coastline: ancient shores can differ — silted harbours such as Ostia or Ephesus now lie inland.',
            ])),
        );
    }
}
