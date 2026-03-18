<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Entity;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * Ultra-lightweight resource for map rendering.
 *
 * Returns a GeoJSON Feature for each entity, suitable for building
 * a FeatureCollection on the client side.
 *
 * @mixin Entity
 */
class EntityMapResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'type' => 'Feature',
            'id' => $this->entity_id,
            'geometry' => $this->geojson ?? $this->geom,
            'properties' => [
                'name' => $this->name,
                'entity_type' => $this->entity_type?->value ?? $this->entity_type,
                'entity_group' => $this->entity_group?->value ?? $this->entity_group,
                'temporal_start' => $this->temporal_start,
                'temporal_end' => $this->temporal_end,
                'display_priority' => $this->display_priority,
                'icon_class' => $this->icon_class?->value ?? $this->icon_class,
                'entity_color' => $this->entity_color,
                'impact_score' => $this->impact_score,
            ],
        ];
    }
}
