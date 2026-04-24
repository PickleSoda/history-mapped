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
        public ?DateResolutionMethod $dateMethod = null,
        public ?ConfidenceLevel $dateConfidence = null,
        public ?DurationType $durationType = null,
        public ?string $locationName = null,
        public ?ConfidenceLevel $locationConfidence = null,
        public ?LocationResolutionMethod $locationMethod = null,
        public ?array $geojson = null,
        public ?array $territoryGeojson = null,
        public ?VerificationStatus $verificationStatus = null,
        public ?ConfidenceLevel $confidence = null,
        public ?int $displayPriority = null,
        public ?IconClass $iconClass = null,
        public ?array $sourceCitations = null,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        // Merge moved fields into the attributes bag
        $attributes = $validated['attributes'] ?? [];

        $movedKeys = ['date_raw', 'confidence_notes', 'entity_color', 'media_refs', 'validation_flags', 'temporal_display_range', 'era_label'];
        foreach ($movedKeys as $key) {
            if (isset($validated[$key])) {
                $attributes[$key] = $validated[$key];
            }
        }

        return new self(
            name: $validated['name'],
            entityType: EntityType::from($validated['entity_type']),
            entityGroup: EntityGroup::from($validated['entity_group']),
            summary: $validated['summary'] ?? null,
            significance: $validated['significance'] ?? null,
            attributes: $attributes ?: null,
            tags: $validated['tags'] ?? null,
            alternativeNames: $validated['alternative_names'] ?? null,
            impactScore: isset($validated['impact_score']) ? (float) $validated['impact_score'] : null,
            wikidataId: $validated['wikidata_id'] ?? null,
            temporalStart: $validated['temporal_start'] ?? null,
            temporalEnd: $validated['temporal_end'] ?? null,
            dateMethod: isset($validated['date_method']) ? DateResolutionMethod::from($validated['date_method']) : null,
            dateConfidence: isset($validated['date_confidence']) ? ConfidenceLevel::from($validated['date_confidence']) : null,
            durationType: isset($validated['duration_type']) ? DurationType::from($validated['duration_type']) : null,
            locationName: $validated['location_name'] ?? null,
            locationConfidence: isset($validated['location_confidence']) ? ConfidenceLevel::from($validated['location_confidence']) : null,
            locationMethod: isset($validated['location_method']) ? LocationResolutionMethod::from($validated['location_method']) : null,
            geojson: $validated['geojson'] ?? null,
            territoryGeojson: $validated['territory_geojson'] ?? null,
            verificationStatus: isset($validated['verification_status']) ? VerificationStatus::from($validated['verification_status']) : null,
            confidence: isset($validated['confidence']) ? ConfidenceLevel::from($validated['confidence']) : null,
            displayPriority: isset($validated['display_priority']) ? (int) $validated['display_priority'] : null,
            iconClass: isset($validated['icon_class']) ? IconClass::from($validated['icon_class']) : null,
            sourceCitations: $validated['source_citations'] ?? null,
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
            'date_method' => $this->dateMethod?->value,
            'date_confidence' => $this->dateConfidence?->value,
            'duration_type' => $this->durationType?->value,
            'location_name' => $this->locationName,
            'location_confidence' => $this->locationConfidence?->value,
            'location_method' => $this->locationMethod?->value,
            'verification_status' => $this->verificationStatus?->value,
            'confidence' => $this->confidence?->value,
            'display_priority' => $this->displayPriority,
            'icon_class' => $this->iconClass?->value,
            'source_citations' => $this->sourceCitations,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        return $data;
    }

    /**
     * Extract the leading signed integer (year) from a temporal text value.
     *
     * Handles plain years ('-0027', '1453') and partial/full ISO dates
     * ('-0480-08', '1453-04-06').
     */
    private static function extractYear(string $temporal): ?int
    {
        if (preg_match('/^-?\d+/', $temporal, $matches)) {
            return (int) $matches[0];
        }

        return null;
    }
}
