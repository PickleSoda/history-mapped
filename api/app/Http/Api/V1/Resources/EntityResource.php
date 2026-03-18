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
        return [
            'id' => $this->entity_id,
            'name' => $this->name,
            'alternative_names' => $this->alternative_names,
            'wikidata_id' => $this->wikidata_id,
            'entity_type' => $this->entity_type?->value,
            'entity_group' => $this->entity_group?->value,

            // Content
            'summary' => $this->summary,
            'significance' => $this->significance,
            'tags' => $this->tags,
            'impact_score' => $this->impact_score,
            'attributes' => $this->attributes,

            // Temporal
            'temporal_start' => $this->temporal_start,
            'temporal_end' => $this->temporal_end,
            'date_raw' => $this->date_raw,
            'date_method' => $this->date_method?->value,
            'date_confidence' => $this->date_confidence?->value,
            'duration_type' => $this->duration_type?->value,
            'temporal_display_range' => $this->temporal_display_range,
            'era_label' => $this->era_label,

            // Spatial
            'location_name' => $this->location_name,
            'location_confidence' => $this->location_confidence?->value,
            'location_method' => $this->location_method?->value,
            'geom' => $this->geom,
            'territory_geom' => $this->when(
                $request->boolean('include_territory'),
                fn () => $this->territory_geom,
            ),

            // Hierarchy
            'parent_entity_id' => $this->parent_entity_id,
            'successor_entity_id' => $this->successor_entity_id,

            // Verification
            'verification_status' => $this->verification_status?->value,
            'confidence' => $this->confidence?->value,
            'confidence_notes' => $this->confidence_notes,
            'validation_flags' => $this->validation_flags,
            'confidence_breakdown' => $this->confidence_breakdown,

            // Display
            'display_priority' => $this->display_priority,
            'icon_class' => $this->icon_class?->value,
            'entity_color' => $this->entity_color,

            // Sources / Media
            'source_citations' => $this->source_citations,
            'media_refs' => $this->media_refs,
            'source_diversity_score' => $this->source_diversity_score,

            // Computed
            'relationship_summary' => $this->relationship_summary,
            'nearby_entity_count' => $this->nearby_entity_count,
            'cluster_id' => $this->cluster_id,

            // Relationships (conditionally loaded)
            'relationships' => $this->when(
                $this->relationLoaded('outgoingRelationships'),
                fn () => RelationshipResource::collection($this->outgoingRelationships),
            ),
            'incoming_relationships' => $this->when(
                $this->relationLoaded('incomingRelationships'),
                fn () => RelationshipResource::collection($this->incomingRelationships),
            ),
            'children' => $this->when(
                $this->relationLoaded('children'),
                fn () => EntitySummaryResource::collection($this->children),
            ),

            // Timestamps
            'created_by' => $this->created_by,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
