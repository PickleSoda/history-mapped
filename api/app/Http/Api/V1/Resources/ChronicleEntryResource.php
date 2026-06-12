<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin \App\Models\ChronicleEntry */
class ChronicleEntryResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'entry_id' => $this->entry_id,
            'sequence_order' => $this->sequence_order,
            'timestamp' => $this->timestamp,
            'start_year' => $this->start_year,
            'end_year' => $this->end_year,
            'impact_score' => $this->impact_score,
            'approximate_location' => $this->approximate_location,
            'narrative_text' => $this->narrative_text,
            'notes' => $this->notes,
            'source_evidence' => $this->source_evidence,
            'primary_relationship' => $this->when(
                $this->relationLoaded('primaryRelationship'),
                fn () => new RelationshipResource($this->primaryRelationship),
            ),
            'secondary_entities' => $this->when(
                $this->relationLoaded('secondaryEntities'),
                fn () => $this->secondaryEntities->map(fn ($e) => [
                    'entity_id' => $e->entity_id,
                    'name' => $e->name,
                    'entity_type' => $e->entity_type?->value,
                    'role' => $e->pivot?->role,
                ]),
            ),
        ];
    }
}
