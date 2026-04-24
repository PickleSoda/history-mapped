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
        public bool $deriveGeometryPeriod = true,
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
            deriveGeometryPeriod: isset($validated['derive_geometry_period']) ? (bool) $validated['derive_geometry_period'] : true,
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
            'start_year' => self::extractYear($this->temporalStart),
            'end_year' => self::extractYear($this->temporalEnd),
            'description' => $this->description,
            'confidence' => $this->confidence?->value,
            'source_citations' => $this->sourceCitations,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        // Always include the boolean toggle (false is a valid value)
        $data['derive_geometry_period'] = $this->deriveGeometryPeriod;

        return $data;
    }

    private static function extractYear(?string $temporal): ?int
    {
        if ($temporal === null || trim($temporal) === '') {
            return null;
        }

        if (! preg_match('/^-?\d+/', $temporal, $matches)) {
            return null;
        }

        return (int) $matches[0];
    }
}
