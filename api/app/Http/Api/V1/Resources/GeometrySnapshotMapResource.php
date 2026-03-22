<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class GeometrySnapshotMapResource extends JsonResource
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
            'geometry' => $this->territory_geojson,
            'properties' => [
                'name' => $this->name,
                'entity_type' => $this->entity_type,
                'entity_group' => $this->entity_group,
                'impact_score' => $this->impact_score,
                'label' => $this->label,
                'confidence' => $this->confidence,
                'display_priority' => $this->display_priority,
            ],
        ];
    }
}
