<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin \App\Models\Chronicle */
class ChronicleResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'chronicle_id' => $this->chronicle_id,
            'title' => $this->title,
            'slug' => $this->slug,
            'source_type' => $this->source_type?->value,
            'source_reference' => $this->source_reference,
            'status' => $this->status?->value,
            'metadata' => $this->metadata,
            'entry_count' => $this->whenCounted('entries'),
            'entries' => $this->when(
                $this->relationLoaded('entries'),
                fn () => ChronicleEntryResource::collection($this->entries),
            ),
            'created_at' => $this->created_at,
            'updated_at' => $this->updated_at,
        ];
    }
}
