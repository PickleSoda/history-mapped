<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ConfidenceLevel;

/**
 * Data Transfer Object for creating or updating a GeometrySnapshot.
 *
 * Used by CreateSnapshotAction and UpdateSnapshotAction.
 * Hydrated from StoreGeometrySnapshotRequest / UpdateGeometrySnapshotRequest validated data.
 */
readonly class GeometrySnapshotData
{
    /**
     * @param  array<string, mixed>|null  $geojson            GeoJSON geometry (Point/LineString)
     * @param  array<string, mixed>|null  $territoryGeojson   GeoJSON geometry (Polygon/MultiPolygon)
     * @param  list<array<string, mixed>>|null  $sourceCitations
     */
    public function __construct(
        public string $entityId,
        public int $yearStart,
        public int $yearEnd,
        public ?array $geojson = null,
        public ?array $territoryGeojson = null,
        public ?string $label = null,
        public ?ConfidenceLevel $confidence = null,
        public ?array $sourceCitations = null,
        public ?string $notes = null,
        public int $displayPriority = 0,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            entityId: $validated['entity_id'],
            yearStart: (int) $validated['year_start'],
            yearEnd: (int) $validated['year_end'],
            geojson: $validated['geojson'] ?? null,
            territoryGeojson: $validated['territory_geojson'] ?? null,
            label: $validated['label'] ?? null,
            confidence: isset($validated['confidence']) ? ConfidenceLevel::from($validated['confidence']) : null,
            sourceCitations: $validated['source_citations'] ?? null,
            notes: $validated['notes'] ?? null,
            displayPriority: isset($validated['display_priority']) ? (int) $validated['display_priority'] : 0,
        );
    }

    /**
     * Convert to array suitable for Eloquent create/update.
     * Geometry columns are excluded — handled via raw PostGIS SQL.
     *
     * @return array<string, mixed>
     */
    public function toModelArray(): array
    {
        $data = [
            'entity_id' => $this->entityId,
            'year_start' => $this->yearStart,
            'year_end' => $this->yearEnd,
            'display_priority' => $this->displayPriority,
        ];

        $optionals = [
            'label' => $this->label,
            'confidence' => $this->confidence?->value,
            'source_citations' => $this->sourceCitations,
            'notes' => $this->notes,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        return $data;
    }
}
