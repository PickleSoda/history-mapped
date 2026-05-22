<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\EntityTimelineEntry;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin EntityTimelineEntry
 */
class EntityTimelineEntrySummaryResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->timeline_entry_id,
            'entity_id' => $this->entity_id,
            'entry_kind' => $this->entry_kind,
            'start_year' => $this->start_year,
            'end_year' => $this->end_year,
            'title' => $this->title,
            'description' => $this->description,
            'location_entity_id' => $this->location_entity_id,
            'has_geom' => (bool) ($this->has_geom ?? false),
            'has_territory_geom' => (bool) ($this->has_territory_geom ?? false),
            'source_table' => $this->source_table,
            'source_id' => $this->source_id,
            'relationship_type' => $this->relationship_type,
            'related_entity_id' => $this->related_entity_id,
            'related_entity_name' => $this->related_entity_name,
            'derived_at' => $this->derived_at?->toISOString(),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}