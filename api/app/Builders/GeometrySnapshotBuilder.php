<?php

declare(strict_types=1);

namespace App\Builders;

use Illuminate\Database\Eloquent\Builder;

/**
 * Custom query builder for GeometrySnapshot model.
 *
 * @template TModel of \App\Models\GeometrySnapshot
 *
 * @extends Builder<TModel>
 */
class GeometrySnapshotBuilder extends Builder
{
    /**
     * Filter snapshots belonging to a specific entity.
     */
    public function forEntity(string $entityId): self
    {
        return $this->where('entity_id', $entityId);
    }

    /**
     * Filter snapshots whose year range includes the given year.
     * Negative values represent BCE years.
     */
    public function atYear(int $year): self
    {
        return $this->where('year_start', '<=', $year)
            ->where('year_end', '>=', $year);
    }

    /**
     * Filter snapshots whose territory geometry intersects a bounding box.
     * Coordinates in SRID 4326 (WGS84 lon/lat).
     */
    public function territoryInBbox(float $minLng, float $minLat, float $maxLng, float $maxLat): self
    {
        return $this->whereRaw(
            'territory_geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)',
            [$minLng, $minLat, $maxLng, $maxLat],
        );
    }

    /**
     * Order chronologically by year_start ascending.
     */
    public function orderChronologically(): self
    {
        return $this->orderBy('year_start');
    }

    /**
     * Select geometry columns as GeoJSON for serialisation.
     * Adds `geom_geojson` and `territory_geom_geojson` virtual columns.
     */
    public function withGeoJson(): self
    {
        return $this->select(['geometry_snapshots.*'])
            ->selectRaw('ST_AsGeoJSON(geom)::jsonb AS geom_geojson')
            ->selectRaw('ST_AsGeoJSON(territory_geom)::jsonb AS territory_geom_geojson');
    }
}
