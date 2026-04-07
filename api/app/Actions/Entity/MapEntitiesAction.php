<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\GeometryPeriod;
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
        * @return array{entities: Collection<int, Entity>, territories: Collection<int, GeometryPeriod>}
     */
    public function __invoke(array $filters): array
    {
        $minImpact = $this->resolveMinImpact($filters);

        $query = Entity::query()
            ->selectForMap()
            ->whereExists(function ($locationQuery): void {
                $locationQuery->selectRaw('1')
                    ->from('entity_locations as el')
                    ->whereColumn('el.entity_id', 'entities.entity_id')
                    ->where('el.is_primary', true)
                    ->whereNotNull('el.geom');
            });

        // Bounding box is required for map queries
        $query->inBbox(
            (float) $filters['bbox_min_lng'],
            (float) $filters['bbox_min_lat'],
            (float) $filters['bbox_max_lng'],
            (float) $filters['bbox_max_lat'],
        );

        // Optional temporal filter
        if (isset($filters['temporal_start'], $filters['temporal_end'])) {
            $query->inTimeRange((int) $filters['temporal_start'], (int) $filters['temporal_end']);
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

        if ($minImpact !== null) {
            $query->where('impact_score', '>=', $minImpact);
        }

        // Only show verified+ by default on map
        $query->verified();

        // Order by display priority for consistent rendering
        $query->orderByDesc('display_priority')->orderByImpact();

        $limit = (int) ($filters['limit'] ?? 2000);

        $entities = $query->limit($limit)->get();

        $territories = collect();

        if ((bool) ($filters['include_territories'] ?? false)) {
            $territoryQuery = GeometryPeriod::query()
                ->with(['entity'])
                ->where('period_type', 'territory')
                ->whereNotNull('territory_geom')
                ->whereRaw(
                    'territory_geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)',
                    [
                        (float) $filters['bbox_min_lng'],
                        (float) $filters['bbox_min_lat'],
                        (float) $filters['bbox_max_lng'],
                        (float) $filters['bbox_max_lat'],
                    ],
                )
                ->whereHas('entity', function ($entityQuery) use ($minImpact): void {
                    $entityQuery->whereIn('verification_status', [
                        VerificationStatus::HumanVerified->value,
                        VerificationStatus::ExpertVerified->value,
                    ]);

                    if ($minImpact !== null) {
                        $entityQuery->where('impact_score', '>=', $minImpact);
                    }
                });

            if (isset($filters['temporal_start'], $filters['temporal_end'])) {
                $territoryQuery
                    ->where('start_year', '<=', (int) $filters['temporal_end'])
                    ->where('end_year', '>=', (int) $filters['temporal_start']);
            }

            $territories = $territoryQuery
                ->orderBy('start_year')
                ->orderBy('end_year')
                ->limit($limit)
                ->get();
        }

        return [
            'entities' => $entities,
            'territories' => $territories,
        ];
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
        if (array_key_exists('min_impact', $filters) && $filters['min_impact'] !== null) {
            return (int) $filters['min_impact'];
        }

        if (isset($filters['zoom_level'])) {
            return ZoomImpactThreshold::forZoom((int) $filters['zoom_level']);
        }

        return null;
    }
}