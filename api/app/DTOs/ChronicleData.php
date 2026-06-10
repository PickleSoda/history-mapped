<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;

/**
 * Data Transfer Object for creating or updating a Chronicle.
 *
 * Used by CreateChronicleAction and UpdateChronicleAction.
 *
 * @param  list<array<string, mixed>>|null  $entries  Each entry: { sequence_order, narrative_text, notes, source_evidence, primary_relationship_id, secondary_entity_ids }
 */
readonly class ChronicleData
{
    public function __construct(
        public string $title,
        public ?string $slug = null,
        public ?SourceType $sourceType = null,
        public ?string $sourceReference = null,
        public ChronicleStatus $status = ChronicleStatus::Draft,
        public ?array $metadata = null,
        public ?array $entries = null,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            title: $validated['title'],
            slug: $validated['slug'] ?? null,
            sourceType: isset($validated['source_type']) ? SourceType::from($validated['source_type']) : null,
            sourceReference: $validated['source_reference'] ?? null,
            status: isset($validated['status']) ? ChronicleStatus::from($validated['status']) : ChronicleStatus::Draft,
            metadata: $validated['metadata'] ?? null,
            entries: $validated['entries'] ?? null,
        );
    }

    /**
     * Convert to array suitable for Eloquent create/update.
     *
     * @return array<string, mixed>
     */
    public function toModelArray(): array
    {
        $data = [
            'title' => $this->title,
            'status' => $this->status->value,
        ];

        if ($this->slug !== null) {
            $data['slug'] = $this->slug;
        }

        if ($this->sourceType !== null) {
            $data['source_type'] = $this->sourceType->value;
        }

        if ($this->sourceReference !== null) {
            $data['source_reference'] = $this->sourceReference;
        }

        if ($this->metadata !== null) {
            $data['metadata'] = $this->metadata;
        }

        return $data;
    }
}
