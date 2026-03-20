<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Services\ZoomImpactThreshold;
use Illuminate\Support\Collection;

/**
 * Retrieve entities optimized for map rendering.
 *
 * Returns lightweight GeoJSON-compatible data using EntityBuilder::selectForMap().
 * Applies spatial (bbox), temporal, type/group, and zoom-level impact threshold filters.
 *
 * Impact threshold logic:
 *   - If `min_impact` is provided it is used directly.
 *   - If only `zoom_level` is provided, the threshold is derived via ZoomImpactThreshold.
 *   - If neither is provided, no impact threshold is applied.
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

        // Zoom-level impact threshold:
        // explicit min_impact takes precedence; otherwise derive from zoom_level.
        $minImpact = $this->resolveMinImpact($filters);

        if ($minImpact !== null) {
            $query->where('impact_score', '>=', $minImpact);
        }

        // Only show verified+ by default on map
        $query->verified();

        // Order by display priority for consistent rendering
        $query->orderByDesc('display_priority')->orderByImpact();

        $limit = (int) ($filters['limit'] ?? 2000);

        return $query->limit($limit)->get();
    }

    /**
     * Resolve the minimum impact score from request filters.
     *
     * Returns null when no threshold should be applied.
     *
     * @param  array<string, mixed>  $filters
     */
    private function resolveMinImpact(array $filters): ?int
    {
        // Explicit override takes precedence
        if (array_key_exists('min_impact', $filters) && $filters['min_impact'] !== null) {
            return (int) $filters['min_impact'];
        }

        // Derive from zoom level
        if (isset($filters['zoom_level'])) {
            return ZoomImpactThreshold::forZoom((int) $filters['zoom_level']);
        }

        return null;
    }
}
