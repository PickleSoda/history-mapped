<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Source;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin Source
 */
class SourceResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->source_id,
            'title' => $this->title,
            'source_type' => $this->source_type?->value,
            'document_type' => $this->document_type,
            'author' => $this->author,
            'date_created' => $this->date_created,
            'date_discovered' => $this->date_discovered,
            'language' => $this->language,
            'current_location' => $this->current_location,
            'source_url' => $this->source_url,
            'content_hash' => $this->content_hash,
            'ingestion_date' => $this->ingestion_date?->toISOString(),

            // Reliability metadata
            'geographic_scope' => $this->geographic_scope,
            'temporal_scope' => $this->temporal_scope,
            'contemporaneity' => $this->contemporaneity,
            'author_bias' => $this->author_bias,
            'corroboration' => $this->corroboration,
            'scholarly_consensus' => $this->scholarly_consensus,

            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
