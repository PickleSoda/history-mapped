<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Services\ZoomImpactThreshold;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

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
    * @return array{entities: Collection<int, Entity>, territories: Collection<int, object>}
     */
    public function __invoke(array $filters): array
    {
        $minImpact = $this->resolveMinImpact($filters);

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

        if (($filters['include_territories'] ?? false) === true) {
            $territories = $this->fetchTerritories($filters, $minImpact, $limit);
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

    /**
     * Retrieve territory snapshots that intersect the requested bounding box.
     *
     * @param  array<string, mixed>  $filters
     * @return Collection<int, object>
     */
    private function fetchTerritories(array $filters, ?int $minImpact, int $limit): Collection
    {
        $query = DB::table('geometry_snapshots as gs')
            ->join('entities as e', 'e.entity_id', '=', 'gs.entity_id')
            ->selectRaw('gs.snapshot_id')
            ->selectRaw('gs.entity_id')
            ->selectRaw('gs.year_start')
            ->selectRaw('gs.year_end')
            ->selectRaw('gs.label')
            ->selectRaw('gs.confidence')
            ->selectRaw('gs.display_priority')
            ->selectRaw('e.name')
            ->selectRaw('e.entity_type')
            ->selectRaw('e.entity_group')
            ->selectRaw('e.impact_score')
            ->selectRaw('ST_AsGeoJSON(gs.territory_geom)::jsonb AS territory_geojson')
            ->whereNotNull('gs.territory_geom')
            ->whereRaw(
                'gs.territory_geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)',
                [
                    (float) $filters['bbox_min_lng'],
                    (float) $filters['bbox_min_lat'],
                    (float) $filters['bbox_max_lng'],
                    (float) $filters['bbox_max_lat'],
                ],
            )
            ->whereIn('e.verification_status', [
                VerificationStatus::HumanVerified->value,
                VerificationStatus::ExpertVerified->value,
            ]);

        if (isset($filters['temporal_start'], $filters['temporal_end'])) {
            $query->where('gs.year_start', '<=', (int) $filters['temporal_end'])
                ->where('gs.year_end', '>=', (int) $filters['temporal_start']);
        }

        if ($minImpact !== null) {
            $query->where('e.impact_score', '>=', $minImpact);
        }

        return $query
            ->orderByDesc('e.impact_score')
            ->orderByDesc('gs.display_priority')
            ->limit($limit)
            ->get();
    }
}
