<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\GeometryPeriod;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin GeometryPeriod
 */
class GeometrySnapshotResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'snapshot_id' => $this->geometry_period_id,
            'entity_id' => $this->entity_id,
            'period_type' => $this->period_type,
            'year_start' => $this->start_year,
            'year_end' => $this->end_year,
            'description' => $this->description,
            'geojson' => $this->geom,
            'territory_geojson' => $this->territory_geom,
            'provenance_mode' => $this->provenance_mode,
            'relationship_id' => $this->relationship_id,
            'source_event_id' => $this->source_event_id,
            'source_table' => 'geometry_periods',
            'source_id' => $this->geometry_period_id,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
