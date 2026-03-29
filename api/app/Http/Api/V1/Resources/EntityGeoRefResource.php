<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\EntityGeoRef;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin EntityGeoRef
 */
class EntityGeoRefResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'geo_ref_id' => $this->geo_ref_id,
            'entity_id' => $this->entity_id,
            'provider' => $this->provider?->value,
            'external_type' => $this->external_type?->value,
            'external_id' => $this->external_id,
            'match_role' => $this->match_role?->value,
            'retrieval_method' => $this->retrieval_method?->value,
            'temporal_start' => $this->temporal_start,
            'temporal_end' => $this->temporal_end,
            'temporal_start_year' => $this->temporal_start_year,
            'temporal_end_year' => $this->temporal_end_year,
            'external_tags' => $this->external_tags,
            'source_meta' => $this->source_meta,
            'match_score' => $this->match_score !== null ? (float) $this->match_score : null,
            'is_active' => $this->is_active,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
