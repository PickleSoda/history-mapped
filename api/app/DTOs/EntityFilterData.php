<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;

/**
 * Data Transfer Object for entity list/search query parameters.
 *
 * Hydrated from ListEntitiesRequest validated data.
 * Passed to ListEntitiesAction which applies filters via EntityBuilder.
 */
readonly class EntityFilterData
{
    /**
     * @param  list<EntityType>|null  $types
     */
    public function __construct(
        public ?string $search = null,
        public ?EntityType $type = null,
        public ?array $types = null,
        public ?EntityGroup $group = null,
        /** @var list<EntityGroup>|null */
        public ?array $groups = null,
        public ?VerificationStatus $status = null,
        public ?ConfidenceLevel $minConfidence = null,
        public ?string $tag = null,
        // Spatial: bounding box
        public ?float $bboxMinLng = null,
        public ?float $bboxMinLat = null,
        public ?float $bboxMaxLng = null,
        public ?float $bboxMaxLat = null,
        // Spatial: near point
        public ?float $nearLng = null,
        public ?float $nearLat = null,
        public ?float $nearRadius = null,
        // Temporal
        public ?int $temporalStart = null,
        public ?int $temporalEnd = null,
        public ?int $existsAt = null,
        // Sorting
        public string $sort = 'relevance',
        // Pagination
        public int $perPage = 25,
        public int $page = 1,
        // Includes
        public bool $includeRelationships = false,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            search: $validated['search'] ?? null,
            type: isset($validated['type']) ? EntityType::from($validated['type']) : null,
            types: isset($validated['types']) ? array_map(
                fn (string $t): EntityType => EntityType::from($t),
                $validated['types'],
            ) : null,
            group: isset($validated['group']) ? EntityGroup::from($validated['group']) : null,
            groups: isset($validated['groups']) ? array_map(
                fn (string $g): EntityGroup => EntityGroup::from($g),
                $validated['groups'],
            ) : null,
            status: isset($validated['status']) ? VerificationStatus::from($validated['status']) : null,
            minConfidence: isset($validated['min_confidence']) ? ConfidenceLevel::from($validated['min_confidence']) : null,
            tag: $validated['tag'] ?? null,
            bboxMinLng: isset($validated['bbox_min_lng']) ? (float) $validated['bbox_min_lng'] : null,
            bboxMinLat: isset($validated['bbox_min_lat']) ? (float) $validated['bbox_min_lat'] : null,
            bboxMaxLng: isset($validated['bbox_max_lng']) ? (float) $validated['bbox_max_lng'] : null,
            bboxMaxLat: isset($validated['bbox_max_lat']) ? (float) $validated['bbox_max_lat'] : null,
            nearLng: isset($validated['near_lng']) ? (float) $validated['near_lng'] : null,
            nearLat: isset($validated['near_lat']) ? (float) $validated['near_lat'] : null,
            nearRadius: isset($validated['near_radius']) ? (float) $validated['near_radius'] : null,
            temporalStart: isset($validated['temporal_start']) ? (int) $validated['temporal_start'] : null,
            temporalEnd: isset($validated['temporal_end']) ? (int) $validated['temporal_end'] : null,
            existsAt: isset($validated['exists_at']) ? (int) $validated['exists_at'] : null,
            sort: $validated['sort'] ?? 'relevance',
            perPage: isset($validated['per_page']) ? (int) $validated['per_page'] : 25,
            page: isset($validated['page']) ? (int) $validated['page'] : 1,
            includeRelationships: (bool) ($validated['include_relationships'] ?? false),
        );
    }

    /**
     * Whether a bounding box filter is fully specified.
     */
    public function hasBbox(): bool
    {
        return $this->bboxMinLng !== null
            && $this->bboxMinLat !== null
            && $this->bboxMaxLng !== null
            && $this->bboxMaxLat !== null;
    }

    /**
     * Whether a near-point filter is fully specified.
     */
    public function hasNearPoint(): bool
    {
        return $this->nearLng !== null
            && $this->nearLat !== null
            && $this->nearRadius !== null;
    }

    /**
     * Whether a temporal range filter is specified.
     */
    public function hasTimeRange(): bool
    {
        return $this->temporalStart !== null
            && $this->temporalEnd !== null;
    }
}
