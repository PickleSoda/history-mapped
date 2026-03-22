<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\GeometrySnapshot;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin GeometrySnapshot
 */
class GeometrySnapshotResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'snapshot_id' => $this->snapshot_id,
            'entity_id' => $this->entity_id,
            'year_start' => $this->year_start,
            'year_end' => $this->year_end,
            'label' => $this->label,
            'description' => $this->description,
            'confidence' => $this->confidence?->value,
            'source_citations' => $this->source_citations,
            'notes' => $this->notes,
            'display_priority' => $this->display_priority,
            'relationship_id' => $this->relationship_id,
            'source_event_id' => $this->source_event_id,
            'geom' => $this->geom,
            'territory_geom' => $this->territory_geom,
            'created_by' => $this->created_by,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
