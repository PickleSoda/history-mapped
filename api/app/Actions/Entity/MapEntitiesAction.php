<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Support\Collection;

/**
 * Retrieve entities optimized for map rendering.
 *
 * Returns lightweight GeoJSON-compatible data using EntityBuilder::selectForMap().
 * Applies spatial (bbox), temporal, and type/group filters.
 */
class MapEntitiesAction
{
    /**
     * @param  array<string, mixed>  $filters
     * @return Collection<int, Entity>
     */
    public function __invoke(array $filters): Collection
    {
        $query = Entity::query()
            ->selectForMap()
            ->whereNotNull('geom');

        // Bounding box is required for map queries
        $query->inBbox(
            (float) $filters['bbox_min_lng'],
            (float) $filters['bbox_min_lat'],
            (float) $filters['bbox_max_lng'],
            (float) $filters['bbox_max_lat'],
        );

        // Optional temporal filter
        if (isset($filters['temporal_start'], $filters['temporal_end'])) {
            $query->inTimeRange($filters['temporal_start'], $filters['temporal_end']);
        }

        // Optional type/group filter
        if (isset($filters['type'])) {
            $query->ofType(EntityType::from($filters['type']));
        }

        if (isset($filters['types']) && is_array($filters['types'])) {
            $query->ofTypes(array_map(
                fn (string $t): EntityType => EntityType::from($t),
                $filters['types'],
            ));
        }

        if (isset($filters['group'])) {
            $query->ofGroup(EntityGroup::from($filters['group']));
        }

        if (isset($filters['min_confidence'])) {
            $query->withMinConfidence(ConfidenceLevel::from($filters['min_confidence']));
        }

        // Only show verified+ by default on map
        $query->verified();

        // Order by display priority for consistent rendering
        $query->orderByDesc('display_priority')->orderByImpact();

        $limit = (int) ($filters['limit'] ?? 2000);

        return $query->limit($limit)->get();
    }
}
