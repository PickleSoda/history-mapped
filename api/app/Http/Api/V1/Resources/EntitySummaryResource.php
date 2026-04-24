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

        // Geometry: withGeoJson() adds geom_geojson as a pre-computed SQL alias.
        // For entities loaded without withGeoJson(), fall back to the primaryLocation relation.
        $geom = $this->geom_geojson
            ?? ($this->relationLoaded('primaryLocation') ? $this->primaryLocation?->geom : null);

        // Tags: withGeoJson() adds entity_tags_json as a JSON-aggregated SQL alias.
        // For entities loaded without withGeoJson(), fall back to the entityTags relation.
        if (array_key_exists('entity_tags_json', $this->getAttributes())) {
            $rawTags = $this->entity_tags_json;
            $tags = is_array($rawTags) ? array_values($rawTags) : (is_string($rawTags) ? json_decode($rawTags, true) ?? [] : []);
        } elseif ($this->relationLoaded('entityTags')) {
            $tags = $this->entityTags->pluck('tag')->values()->all();
        } else {
            $tags = [];
        }

        return [
            'id' => $this->entity_id,
            'name' => $this->name,
            'entity_type' => $this->entity_type?->value,
            'entity_group' => $this->entity_group?->value,
            'summary' => $this->summary,
            'tags' => $tags,
            'impact_score' => $this->impact_score,

            // Temporal (compact) — populated via withGeoJson() SQL aliases
            'temporal_start' => $this->temporal_start,
            'temporal_end' => $this->temporal_end,
            'temporal_display_range' => $attrs['temporal_display_range'] ?? null,
            'era_label' => $attrs['era_label'] ?? null,

            // Spatial (point only)
            'location_name' => $this->location_name,
            'geom' => $geom,

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
