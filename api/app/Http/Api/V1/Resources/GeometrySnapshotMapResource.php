<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\GeometryPeriod;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin GeometryPeriod
 */
class GeometrySnapshotMapResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'snapshot_id' => $this->geometry_period_id,
            'entity_id' => $this->entity_id,
            'year_start' => $this->start_year,
            'year_end' => $this->end_year,
            'geojson' => $this->geom,
            'territory_geojson' => $this->territory_geom,
            'source_table' => 'geometry_periods',
            'source_id' => $this->geometry_period_id,
        ];
    }
}
