<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Services\ZoomImpactThreshold;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * Retrieve map border features from geometry periods.
 *
 * Applies spatial (bbox), temporal, entity metadata filters, and zoom-level impact thresholds.
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
     * @return array{features: Collection<int, array<string, mixed>>}
     */
    public function __invoke(array $filters): array
    {
        $minImpact = $this->resolveMinImpact($filters);
        $year = $this->resolveYear($filters);
        $limit = (int) ($filters['limit'] ?? 2000);

        // Clamp limit for global bboxes to prevent excessive data transfer
        if ($this->isGlobalBbox($filters)) {
            $limit = min($limit, 75);
        }

        // Query geometry_periods directly (map borders source of truth),
        // enrich with entity metadata and primary alias display name.
        $query = DB::table('geometry_periods')
            ->selectRaw(
                <<<'SQL'
                geometry_periods.geometry_period_id,
                entities.entity_id,
                geometry_periods.start_year,
                geometry_periods.end_year,
                geometry_periods.period_type,
                COALESCE(
                    (
                        SELECT entity_aliases.name
                        FROM entity_aliases
                        WHERE entity_aliases.entity_id = entities.entity_id
                          AND entity_aliases.is_primary = true
                        ORDER BY entity_aliases.updated_at DESC NULLS LAST, entity_aliases.created_at DESC NULLS LAST
                        LIMIT 1
                    ),
                    entities.name
                ) AS display_name,
                entities.entity_type,
                entities.entity_group,
                entities.display_priority,
                entities.icon_class,
                entities.impact_score,
                ST_AsGeoJSON(COALESCE(geometry_periods.territory_geom, geometry_periods.geom))::text AS geojson
                SQL
            )
            ->join('entities', 'entities.entity_id', '=', 'geometry_periods.entity_id')
            ->where('geometry_periods.start_year', '<=', $year)
            ->where('geometry_periods.end_year', '>=', $year)
            ->where(function ($spatialTypeQuery): void {
                $spatialTypeQuery
                    ->whereNotNull('geometry_periods.territory_geom')
                    ->orWhereNotNull('geometry_periods.geom');
            });

        // Apply entity filters FIRST (before spatial filtering for best performance)
        $query->whereIn('entities.verification_status', [
            VerificationStatus::PipelineDraft->value,
            VerificationStatus::OhmDraft->value,
            VerificationStatus::AutoValidated->value,
            VerificationStatus::NeedsReview->value,
            VerificationStatus::InReview->value,
            VerificationStatus::HumanVerified->value,
            VerificationStatus::ExpertVerified->value,
        ]);

        if ($minImpact !== null) {
            $query->where('entities.impact_score', '>=', $minImpact);
        }

        // Optional type filter
        if (isset($filters['type'])) {
            $query->where('entities.entity_type', EntityType::from($filters['type'])->value);
        }

        if (isset($filters['types']) && is_array($filters['types'])) {
            $typeValues = array_map(
                fn (string $t): string => EntityType::from($t)->value,
                $filters['types'],
            );
            $query->whereIn('entities.entity_type', $typeValues);
        }

        if (isset($filters['min_confidence'])) {
            $query->where('entities.confidence', '>=', ConfidenceLevel::from($filters['min_confidence'])->value);
        }

        // Optional temporal range filter (overrides single-year filter when provided)
        if (isset($filters['temporal_start'], $filters['temporal_end'])) {
            $query->where('geometry_periods.start_year', '<=', (int) $filters['temporal_end'])
                ->where('geometry_periods.end_year', '>=', (int) $filters['temporal_start']);
        }

        // Filter by spatial bbox on border geometry columns
        $bbox = [
            (float) $filters['bbox_min_lng'],
            (float) $filters['bbox_min_lat'],
            (float) $filters['bbox_max_lng'],
            (float) $filters['bbox_max_lat'],
        ];

        $query->whereRaw(
            '(geometry_periods.territory_geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)
              OR geometry_periods.geom && ST_MakeEnvelope(?, ?, ?, ?, 4326))',
            [...$bbox, ...$bbox],
        );

        // Prefer explicit border geometry first, then entity priority.
        $query
            ->orderByRaw('CASE WHEN geometry_periods.territory_geom IS NOT NULL THEN 0 ELSE 1 END')
            ->orderByDesc('entities.display_priority')
            ->orderByDesc('geometry_periods.start_year')
            ->orderBy('geometry_periods.end_year');

        $rows = $query->limit($limit)->get();

        $features = $rows->map(function ($row): array {
            $geometry = null;

            if (is_string($row->geojson) && $row->geojson !== '') {
                $decoded = json_decode($row->geojson, true);
                if (is_array($decoded)) {
                    $geometry = $decoded;
                }
            }

            return [
                'type' => 'Feature',
                'id' => $row->entity_id,
                'geometry' => $geometry,
                'properties' => [
                    'id' => $row->entity_id,
                    'name' => $row->display_name,
                    'entity_type' => $row->entity_type,
                    'entity_group' => $row->entity_group,
                    'impact_score' => $row->impact_score,
                    'display_priority' => $row->display_priority,
                    'icon_class' => $row->icon_class,
                    'period_type' => $row->period_type,
                    'geometry_period_id' => $row->geometry_period_id,
                    'start_year' => $row->start_year,
                    'end_year' => $row->end_year,
                ],
            ];
        })->values();

        return ['features' => $features];
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

    /**
     * @param  array<string, mixed>  $filters
     */
    private function resolveYear(array $filters): int
    {
        return array_key_exists('year', $filters)
            ? (int) $filters['year']
            : 1000;
    }

    /**
     * Check if the provided bbox covers the whole world (approximately).
     *
     * @param  array<string, mixed>  $filters
     */
    private function isGlobalBbox(array $filters): bool
    {
        return ((float) $filters['bbox_min_lng'] ?? 0) <= -179
            && ((float) $filters['bbox_max_lng'] ?? 0) >= 179
            && ((float) $filters['bbox_min_lat'] ?? 0) <= -84
            && ((float) $filters['bbox_max_lat'] ?? 0) >= 84;
    }
}