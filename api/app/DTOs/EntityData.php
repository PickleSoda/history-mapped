<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;

/**
 * Data Transfer Object for creating or updating an Entity.
 *
 * Used by CreateEntityAction and UpdateEntityAction.
 * Hydrated from StoreEntityRequest / UpdateEntityRequest validated data.
 */
readonly class EntityData
{
    /**
     * @param  list<string>|null  $tags
     * @param  list<string>|null  $alternativeNames
     * @param  array<string, mixed>|null  $attributes
     * @param  array<string, mixed>|null  $geojson       GeoJSON geometry object for point location
     * @param  array<string, mixed>|null  $territoryGeojson  GeoJSON geometry for territory/area
     * @param  list<array<string, mixed>>|null  $sourceCitations
     * @param  list<array<string, mixed>>|null  $mediaRefs
     */
    public function __construct(
        public string $name,
        public EntityType $entityType,
        public EntityGroup $entityGroup,
        public ?string $summary = null,
        public ?string $significance = null,
        public ?array $attributes = null,
        public ?array $tags = null,
        public ?array $alternativeNames = null,
        public ?float $impactScore = null,
        public ?string $wikidataId = null,
        public ?string $temporalStart = null,
        public ?string $temporalEnd = null,
        public ?string $dateRaw = null,
        public ?DateResolutionMethod $dateMethod = null,
        public ?ConfidenceLevel $dateConfidence = null,
        public ?DurationType $durationType = null,
        public ?string $locationName = null,
        public ?ConfidenceLevel $locationConfidence = null,
        public ?LocationResolutionMethod $locationMethod = null,
        public ?array $geojson = null,
        public ?array $territoryGeojson = null,
        public ?string $parentEntityId = null,
        public ?string $successorEntityId = null,
        public ?VerificationStatus $verificationStatus = null,
        public ?ConfidenceLevel $confidence = null,
        public ?string $confidenceNotes = null,
        public ?int $displayPriority = null,
        public ?IconClass $iconClass = null,
        public ?string $entityColor = null,
        public ?array $sourceCitations = null,
        public ?array $mediaRefs = null,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            name: $validated['name'],
            entityType: EntityType::from($validated['entity_type']),
            entityGroup: EntityGroup::from($validated['entity_group']),
            summary: $validated['summary'] ?? null,
            significance: $validated['significance'] ?? null,
            attributes: $validated['attributes'] ?? null,
            tags: $validated['tags'] ?? null,
            alternativeNames: $validated['alternative_names'] ?? null,
            impactScore: isset($validated['impact_score']) ? (float) $validated['impact_score'] : null,
            wikidataId: $validated['wikidata_id'] ?? null,
            temporalStart: $validated['temporal_start'] ?? null,
            temporalEnd: $validated['temporal_end'] ?? null,
            dateRaw: $validated['date_raw'] ?? null,
            dateMethod: isset($validated['date_method']) ? DateResolutionMethod::from($validated['date_method']) : null,
            dateConfidence: isset($validated['date_confidence']) ? ConfidenceLevel::from($validated['date_confidence']) : null,
            durationType: isset($validated['duration_type']) ? DurationType::from($validated['duration_type']) : null,
            locationName: $validated['location_name'] ?? null,
            locationConfidence: isset($validated['location_confidence']) ? ConfidenceLevel::from($validated['location_confidence']) : null,
            locationMethod: isset($validated['location_method']) ? LocationResolutionMethod::from($validated['location_method']) : null,
            geojson: $validated['geojson'] ?? null,
            territoryGeojson: $validated['territory_geojson'] ?? null,
            parentEntityId: $validated['parent_entity_id'] ?? null,
            successorEntityId: $validated['successor_entity_id'] ?? null,
            verificationStatus: isset($validated['verification_status']) ? VerificationStatus::from($validated['verification_status']) : null,
            confidence: isset($validated['confidence']) ? ConfidenceLevel::from($validated['confidence']) : null,
            confidenceNotes: $validated['confidence_notes'] ?? null,
            displayPriority: isset($validated['display_priority']) ? (int) $validated['display_priority'] : null,
            iconClass: isset($validated['icon_class']) ? IconClass::from($validated['icon_class']) : null,
            entityColor: $validated['entity_color'] ?? null,
            sourceCitations: $validated['source_citations'] ?? null,
            mediaRefs: $validated['media_refs'] ?? null,
        );
    }

    /**
     * Convert to array suitable for Eloquent create/update.
     * Excludes null values so partial updates work correctly.
     *
     * @return array<string, mixed>
     */
    public function toModelArray(): array
    {
        $data = [
            'name' => $this->name,
            'entity_type' => $this->entityType->value,
            'entity_group' => $this->entityGroup->value,
        ];

        // Optional scalar fields — only include if not null
        $optionals = [
            'summary' => $this->summary,
            'significance' => $this->significance,
            'attributes' => $this->attributes,
            'tags' => $this->tags,
            'alternative_names' => $this->alternativeNames,
            'impact_score' => $this->impactScore,
            'wikidata_id' => $this->wikidataId,
            'temporal_start' => $this->temporalStart,
            'temporal_end' => $this->temporalEnd,
            'date_raw' => $this->dateRaw,
            'date_method' => $this->dateMethod?->value,
            'date_confidence' => $this->dateConfidence?->value,
            'duration_type' => $this->durationType?->value,
            'location_name' => $this->locationName,
            'location_confidence' => $this->locationConfidence?->value,
            'location_method' => $this->locationMethod?->value,
            'parent_entity_id' => $this->parentEntityId,
            'successor_entity_id' => $this->successorEntityId,
            'verification_status' => $this->verificationStatus?->value,
            'confidence' => $this->confidence?->value,
            'confidence_notes' => $this->confidenceNotes,
            'display_priority' => $this->displayPriority,
            'icon_class' => $this->iconClass?->value,
            'entity_color' => $this->entityColor,
            'source_citations' => $this->sourceCitations,
            'media_refs' => $this->mediaRefs,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        return $data;
    }
}
