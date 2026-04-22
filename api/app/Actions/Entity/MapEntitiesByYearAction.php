<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use Illuminate\Support\LazyCollection;
use Illuminate\Support\Facades\DB;

class MapEntitiesByYearAction
{
    /**
     * @param  array<string, mixed>  $filters
     * @return array{features: LazyCollection<int, array<string, mixed>>}
     */
    public function __invoke(array $filters): array
    {
        $year = (int) $filters['year'];
        $limit = (int) ($filters['limit'] ?? 100000);

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
                ST_AsGeoJSON(COALESCE(geometry_periods.territory_geom, geometry_periods.geom), 5)::text AS geojson
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

        $query->whereIn('entities.verification_status', [
            VerificationStatus::PipelineDraft->value,
            VerificationStatus::OhmDraft->value,
            VerificationStatus::AutoValidated->value,
            VerificationStatus::NeedsReview->value,
            VerificationStatus::InReview->value,
            VerificationStatus::HumanVerified->value,
            VerificationStatus::ExpertVerified->value,
        ]);

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

        if (isset($filters['min_impact']) && $filters['min_impact'] !== null) {
            $query->where('entities.impact_score', '>=', (int) $filters['min_impact']);
        }

        $query
            ->orderByRaw('CASE WHEN geometry_periods.territory_geom IS NOT NULL THEN 0 ELSE 1 END')
            ->orderByDesc('entities.display_priority')
            ->orderByDesc('geometry_periods.start_year')
            ->orderBy('geometry_periods.end_year');

        $features = $query->limit($limit)->cursor()->map(function ($row): array {
            return [
                'id' => $row->entity_id,
                'geometry_json' => is_string($row->geojson) && $row->geojson !== '' ? $row->geojson : 'null',
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
        });

        return ['features' => $features];
    }
}
