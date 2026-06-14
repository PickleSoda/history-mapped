<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Entity;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * JSON:API resource for a single Entity.
 *
 * Used for show/create/update responses where full detail is needed.
 *
 * @mixin Entity
 */
class EntityResource extends JsonResource
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
            'alternative_names' => $this->whenLoaded('aliases', fn () => $this->aliases->pluck('name')->values()->all(), []),
            'wikidata_id' => $this->wikidata_id,
            'entity_type' => $this->entity_type?->value,
            'entity_group' => $this->entity_group?->value,

            // Content
            'summary' => $this->summary,
            'significance' => $this->significance,
            'tags' => $this->whenLoaded('entityTags', fn () => $this->entityTags->pluck('tag')->values()->all(), []),
            'impact_score' => $this->impact_score,
            'attributes' => $attrs,

            // Temporal
            'temporal_start' => $this->whenLoaded('primaryTemporalRange', fn () => $this->primaryTemporalRange?->start_date),
            'temporal_end' => $this->whenLoaded('primaryTemporalRange', fn () => $this->primaryTemporalRange?->end_date),
            'date_raw' => $attrs['date_raw'] ?? null,
            'date_method' => $this->date_method?->value,
            'date_confidence' => $this->date_confidence?->value,
            'duration_type' => $this->duration_type?->value,
            'temporal_display_range' => $attrs['temporal_display_range'] ?? null,
            'era_label' => $attrs['era_label'] ?? null,

            // Spatial
            'location_name' => $this->whenLoaded('primaryLocation', fn () => $this->primaryLocation?->location_name),
            'location_confidence' => $this->location_confidence?->value,
            'location_method' => $this->location_method?->value,
            'geom' => $this->whenLoaded('primaryLocation', fn () => $this->primaryLocation?->geom),
            'territory_geom' => $this->when(
                $request->boolean('include_territory') && $this->relationLoaded('primaryLocation'),
                fn () => $this->primaryLocation?->territory_geom,
            ),

            // Verification
            'verification_status' => $this->verification_status?->value,
            'confidence' => $this->confidence?->value,
            'confidence_notes' => $attrs['confidence_notes'] ?? null,
            'validation_flags' => $attrs['validation_flags'] ?? null,

            // Display
            'display_priority' => $this->display_priority,
            'icon_class' => $this->icon_class?->value,
            'entity_color' => $attrs['entity_color'] ?? null,

            // Sources / Media
            'source_citations' => $this->source_citations,
            'media_refs' => $attrs['media_refs'] ?? null,
            'geometry_periods_count' => $this->geometry_periods_count,
            'timeline_entries_count' => $this->timeline_entries_count,

            // Relationships (conditionally loaded)
            'relationships' => $this->when(
                $this->relationLoaded('outgoingRelationships'),
                fn () => RelationshipResource::collection($this->outgoingRelationships),
            ),
            'incoming_relationships' => $this->when(
                $this->relationLoaded('incomingRelationships'),
                fn () => RelationshipResource::collection($this->incomingRelationships),
            ),
            // Timestamps
            'created_by' => $this->created_by,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
