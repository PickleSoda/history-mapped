<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Entity;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * Lightweight Entity resource for list/collection responses.
 *
 * Omits heavy fields (attributes, territory_geom, citations) for performance.
 *
 * @mixin Entity
 */
class EntitySummaryResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        $attrs = $this->attributes ?? [];

        return [
            'id' => $this->entity_id,
            'name' => $this->name,
            'entity_type' => $this->entity_type?->value,
            'entity_group' => $this->entity_group?->value,
            'summary' => $this->summary,
            'tags' => $this->tags,
            'impact_score' => $this->impact_score,

            // Temporal (compact)
            'temporal_start' => $this->temporal_start,
            'temporal_end' => $this->temporal_end,
            'temporal_display_range' => $attrs['temporal_display_range'] ?? null,
            'era_label' => $attrs['era_label'] ?? null,

            // Spatial (point only)
            'location_name' => $this->location_name,
            'geom' => $this->geom,

            // Verification
            'verification_status' => $this->verification_status?->value,
            'confidence' => $this->confidence?->value,

            // Display
            'display_priority' => $this->display_priority,
            'icon_class' => $this->icon_class?->value,
            'entity_color' => $attrs['entity_color'] ?? null,

            'created_at' => $this->created_at?->toISOString(),
        ];
    }
}
