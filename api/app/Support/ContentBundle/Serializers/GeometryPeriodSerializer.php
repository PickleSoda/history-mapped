<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Models\GeometryPeriod;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

/**
 * Geometry period -> bundle line. Geometry is selected as GeoJSON (`<col>_geojson`), never as the
 * raw geometry column.
 */
final class GeometryPeriodSerializer implements RecordSerializer
{
    private const COLUMNS = [
        'geometry_period_id', 'entity_id', 'period_type', 'start_year', 'end_year', 'description',
        'confidence', 'provenance_mode', 'relationship_id', 'source_event_id',
    ];

    public function type(): RecordType
    {
        return RecordType::GeometryPeriods;
    }

    public function query(): Builder
    {
        return GeometryPeriod::query()
            ->select((new GeometryPeriod)->qualifyColumns(self::COLUMNS))
            ->selectRaw('ST_AsGeoJSON(geometry_periods.geom, 7) as geom_geojson')
            ->selectRaw('ST_AsGeoJSON(geometry_periods.territory_geom, 7) as territory_geom_geojson');
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof GeometryPeriod);
        $r = fn (string $col) => Values::raw($model, $col);

        return [
            'id' => $r('geometry_period_id'),
            'entity_id' => $r('entity_id'),
            'period_type' => $r('period_type'),
            'start_year' => $r('start_year'),
            'end_year' => $r('end_year'),
            'description' => $r('description'),
            'confidence' => $r('confidence'),
            'provenance_mode' => $r('provenance_mode'),
            'relationship_id' => $r('relationship_id'),
            'source_event_id' => $r('source_event_id'),
            'geom' => Values::geojson($model, 'geom'),
            'territory_geom' => Values::geojson($model, 'territory_geom'),
        ];
    }
}
