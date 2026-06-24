<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\LazyCollection;

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
        // One feature per entity (MQ-16) unless ?all_periods is requested.
        $allPeriods = (bool) ($filters['all_periods'] ?? false);

        // OHM geo-ref subqueries (primary first) — mirrors MapEntitiesAction so
        // both map endpoints carry the same OHM ref contract. For OHM-linked
        // entities the client highlights the OHM basemap feature, so we serve the
        // point geometry instead of the stored polygon (borders-from-OHM, D19).
        $ohmWhere = "egr.entity_id = entities.entity_id AND egr.provider = 'ohm' AND egr.is_active = true";
        $ohmOrder = "ORDER BY (egr.match_role = 'primary') DESC, egr.updated_at DESC NULLS LAST LIMIT 1";
        $ohmExternalId = "(SELECT egr.external_id FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder})";
        $ohmExternalType = "(SELECT egr.external_type::text FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder})";
        $ohmExists = "EXISTS (SELECT 1 FROM entity_geo_refs egr WHERE {$ohmWhere})";
        $geom = "CASE WHEN {$ohmExists} THEN geometry_periods.geom ELSE COALESCE(geometry_periods.territory_geom, geometry_periods.geom) END";

        // display_priority/impact_score are selected for the outer curation order.
        $columns = <<<SQL
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
            entities.impact_score,
            entities.attributes->>'entity_color' AS entity_color,
            {$ohmExternalId} AS ohm_external_id,
            {$ohmExternalType} AS ohm_external_type,
            ST_AsGeoJSON({$geom}, 5)::text AS geojson
            SQL;

        $query = DB::table('geometry_periods')
            // One row per entity (MQ-16) via DISTINCT ON unless all periods asked.
            ->selectRaw(($allPeriods ? '' : 'DISTINCT ON (entities.entity_id) ').$columns)
            ->join('entities', 'entities.entity_id', '=', 'geometry_periods.entity_id')
            // int4range temporal predicate (index-usable, MQ-7); NULL end = ongoing.
            // EVENTs are decade-sticky: their momentary point is padded ±10y so it
            // surfaces near its time on the continuous timeline (see MapEntitiesAction).
            ->whereRaw(
                'int4range('
                ."CASE WHEN entities.entity_group = 'EVENT' THEN geometry_periods.start_year - 10 ELSE geometry_periods.start_year END, "
                ."CASE WHEN entities.entity_group = 'EVENT' THEN COALESCE(geometry_periods.end_year, geometry_periods.start_year) + 11 "
                ."WHEN geometry_periods.end_year IS NULL THEN NULL ELSE geometry_periods.end_year + 1 END, '[)') @> ?::integer",
                [$year],
            )
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
            $query->whereIn(
                'entities.confidence',
                ConfidenceLevel::atLeast(ConfidenceLevel::from($filters['min_confidence'])),
            );
        }

        if (isset($filters['min_impact']) && $filters['min_impact'] !== null) {
            $query->where('entities.impact_score', '>=', (int) $filters['min_impact']);
        }

        // Optional entity-group filter (multi-group `groups[]` or single `group`) — MQ-13.
        if (isset($filters['groups']) && is_array($filters['groups'])) {
            $groupValues = array_map(
                fn (string $g): string => EntityGroup::from($g)->value,
                $filters['groups'],
            );
            $query->whereIn('entities.entity_group', $groupValues);
        } elseif (isset($filters['group'])) {
            $query->where('entities.entity_group', EntityGroup::from($filters['group'])->value);
        }

        if ($allPeriods) {
            // Every period; territory-first then priority (NULLS LAST), newest first.
            $rows = $query
                ->orderByRaw('CASE WHEN geometry_periods.territory_geom IS NOT NULL THEN 0 ELSE 1 END')
                ->orderByRaw('entities.display_priority DESC NULLS LAST')
                ->orderByDesc('geometry_periods.start_year')
                ->orderBy('geometry_periods.end_year')
                ->limit($limit)
                ->cursor();
        } else {
            // DISTINCT ON requires the dedup key to lead the ORDER BY; the inner
            // tiebreak picks the territory period, newest start, for each entity.
            $query->orderByRaw(
                'entities.entity_id, (geometry_periods.territory_geom IS NULL), geometry_periods.start_year DESC, geometry_periods.end_year ASC NULLS FIRST',
            );

            // Re-order the deduped rows by display priority then impact (MQ-15).
            $rows = DB::query()
                ->fromSub($query, 'm')
                ->orderByRaw('m.display_priority DESC NULLS LAST, m.impact_score DESC NULLS LAST')
                ->limit($limit)
                ->cursor();
        }

        $periodFeatures = $rows->map(function ($row): array {
            return [
                'id' => $row->entity_id,
                'geometry_json' => is_string($row->geojson) && $row->geojson !== '' ? $row->geojson : 'null',
                'properties' => [
                    'id' => $row->entity_id,
                    'name' => $row->display_name,
                    'entity_type' => $row->entity_type,
                    'entity_group' => $row->entity_group,
                    'impact_score' => $row->impact_score,
                    'start_year' => $row->start_year,
                    'end_year' => $row->end_year,
                    'entity_color' => $row->entity_color,
                    'ohm_provider' => $row->ohm_external_id !== null ? 'ohm' : null,
                    'ohm_external_type' => $row->ohm_external_type,
                    'ohm_external_id' => $row->ohm_external_id,
                ],
            ];
        });

        return ['features' => $periodFeatures];
    }
}
