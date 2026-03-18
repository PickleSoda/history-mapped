<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;

/**
 * Data Transfer Object for creating an EntityRelationship.
 */
readonly class RelationshipData
{
    /**
     * @param  list<array<string, mixed>>|null  $sourceCitations
     */
    public function __construct(
        public string $sourceEntityId,
        public string $targetEntityId,
        public RelationshipType $relationshipType,
        public ?string $temporalStart = null,
        public ?string $temporalEnd = null,
        public ?string $description = null,
        public ?ConfidenceLevel $confidence = null,
        public ?array $sourceCitations = null,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            sourceEntityId: $validated['source_entity_id'],
            targetEntityId: $validated['target_entity_id'],
            relationshipType: RelationshipType::from($validated['relationship_type']),
            temporalStart: $validated['temporal_start'] ?? null,
            temporalEnd: $validated['temporal_end'] ?? null,
            description: $validated['description'] ?? null,
            confidence: isset($validated['confidence']) ? ConfidenceLevel::from($validated['confidence']) : null,
            sourceCitations: $validated['source_citations'] ?? null,
        );
    }

    /**
     * @return array<string, mixed>
     */
    public function toModelArray(): array
    {
        $data = [
            'source_entity_id' => $this->sourceEntityId,
            'target_entity_id' => $this->targetEntityId,
            'relationship_type' => $this->relationshipType->value,
        ];

        $optionals = [
            'temporal_start' => $this->temporalStart,
            'temporal_end' => $this->temporalEnd,
            'description' => $this->description,
            'confidence' => $this->confidence?->value,
            'source_citations' => $this->sourceCitations,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        return $data;
    }
}
