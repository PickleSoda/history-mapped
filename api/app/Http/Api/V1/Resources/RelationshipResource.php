<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\EntityRelationship;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin EntityRelationship
 */
class RelationshipResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->relationship_id,
            'source_entity_id' => $this->source_entity_id,
            'target_entity_id' => $this->target_entity_id,
            'relationship_type' => $this->relationship_type?->value,
            'temporal_start' => $this->temporal_start,
            'temporal_end' => $this->temporal_end,
            'description' => $this->description,
            'confidence' => $this->confidence?->value,
            'source_citations' => $this->source_citations,

            // Conditionally include related entities (summary form)
            'source_entity' => $this->when(
                $this->relationLoaded('sourceEntity'),
                fn () => new EntitySummaryResource($this->sourceEntity),
            ),
            'target_entity' => $this->when(
                $this->relationLoaded('targetEntity'),
                fn () => new EntitySummaryResource($this->targetEntity),
            ),

            'created_at' => $this->created_at?->toISOString(),
            'created_by' => $this->created_by,
        ];
    }
}
