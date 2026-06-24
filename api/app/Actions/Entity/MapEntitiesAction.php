<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Services\ZoomImpactThreshold;
use App\Services\ZoomSimplification;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\LazyCollection;

/**
 * Retrieve map border features from geometry periods.
 *
 * Applies spatial (bbox), temporal, entity metadata filters, and zoom-level impact thresholds.
 *
 * Impact threshold logic:
 *   - If `min_impact` is provided it is used directly.
 *   - If only `zoom_level` is provided, the threshold is derived via ZoomImpactThreshold.
 *   - If neither is provided, no impact threshold is applied.
 *
 * Minimum-results floor (`min_results`): when a threshold is active, the result
 * is the union of entities above the threshold and the top-`min_results` by
 * impact in view — so the map is never empty when zoomed out or filtered, while
 * the threshold still declutters wherever plenty clears it. Off when 0/omitted.
 */
class MapEntitiesAction
{
    /**
     * @param  array<string, mixed>  $filters
     * @return array{features: LazyCollection<int, array<string, mixed>>}
     */
    public function __invoke(array $filters): array
    {
        $minImpact = $this->resolveMinImpact($filters);
        $limit = (int) ($filters['limit'] ?? 2000);
        // One feature per entity (MQ-16) unless ?all_periods is requested.
        $allPeriods = (bool) ($filters['all_periods'] ?? false);

        // Minimum-results floor: when a threshold is active but few entities clear
        // it, keep the map populated by also returning the next highest-impact
        // ones up to this count. The threshold then declutters only where there is
        // plenty above it. Off (0) unless requested; not applied to all_periods.
        $floor = max(0, (int) ($filters['min_results'] ?? 0));
        $backfill = $minImpact !== null && $floor > 0 && ! $allPeriods;

        // Borders-from-OHM (§3.1): OHM-linked entities serialize their point so
        // the client can highlight the OHM basemap feature instead of a stored
        // polygon. Active OHM geo-ref subqueries (primary first).
        $ohmWhere = "egr.entity_id = entities.entity_id AND egr.provider = 'ohm' AND egr.is_active = true";
        $ohmOrder = "ORDER BY (egr.match_role = 'primary') DESC, egr.updated_at DESC NULLS LAST LIMIT 1";
        $ohmExternalId = "(SELECT egr.external_id FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder})";
        $ohmExternalType = "(SELECT egr.external_type::text FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder})";
        $ohmExists = "EXISTS (SELECT 1 FROM entity_geo_refs egr WHERE {$ohmWhere})";

        // Geometry served: the point for OHM-linked entities, else the app-owned
        // COALESCE(territory_geom, geom). Zoom simplification (MQ-6) applies only
        // to non-point geometry (ST_Dimension > 0).
        $simplify = ZoomSimplification::forZoom((int) ($filters['zoom_level'] ?? 12));
        $geom = "CASE WHEN {$ohmExists} THEN geometry_periods.geom ELSE COALESCE(geometry_periods.territory_geom, geometry_periods.geom) END";
        $geojsonExpr = $simplify['tolerance'] > 0
            ? "ST_AsGeoJSON(CASE WHEN ST_Dimension({$geom}) = 0 THEN {$geom} ELSE ST_SimplifyPreserveTopology({$geom}, {$simplify['tolerance']}) END, {$simplify['digits']})::text AS geojson"
            : "ST_AsGeoJSON({$geom}, {$simplify['digits']})::text AS geojson";

        // display_priority/impact_score are selected for ordering; the output
        // properties are trimmed to the UI contract (MQ-8) + entity_color + OHM ref.
        $columns = <<<SQL
            entities.entity_id,
            geometry_periods.start_year,
            geometry_periods.end_year,
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
            SQL;
        $columns .= "\n            ".$geojsonExpr;

        // Query geometry_periods directly (map borders source of truth),
        // enrich with entity metadata and primary alias display name.
        $query = DB::table('geometry_periods')
            ->selectRaw(($allPeriods ? '' : 'DISTINCT ON (entities.entity_id) ').$columns)
            ->join('entities', 'entities.entity_id', '=', 'geometry_periods.entity_id')
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

        // When backfilling, the threshold is applied later (as a soft floor over
        // the ranked rows) so entities below it can still fill the quota.
        if ($minImpact !== null && ! $backfill) {
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
            $query->whereIn(
                'entities.confidence',
                ConfidenceLevel::atLeast(ConfidenceLevel::from($filters['min_confidence'])),
            );
        }

        // Optional entity-group filter (multi-group `groups[]` or single `group`).
        if (isset($filters['groups']) && is_array($filters['groups'])) {
            $groupValues = array_map(
                fn (string $g): string => EntityGroup::from($g)->value,
                $filters['groups'],
            );
            $query->whereIn('entities.entity_group', $groupValues);
        } elseif (isset($filters['group'])) {
            $query->where('entities.entity_group', EntityGroup::from($filters['group'])->value);
        }

        // Temporal predicate via int4range (mirrors gp_active_range_gist_idx, so
        // it is index-usable; MQ-7). A range REPLACES the single-year filter
        // (MQ-1); presence of year-or-range is guaranteed by MapEntitiesRequest.
        // A NULL end_year is unbounded above (ongoing); a NULL start unbounded below.
        //
        // EVENTs are momentary points (start = end) but the timeline is continuous,
        // so an exact-year match would flash by on a scrub. They're "decade-sticky":
        // their effective range is padded ±10y around the point (or span) so the
        // event surfaces near its time without bleeding across a whole century. The
        // stored period stays a precise point — only the match widens. The CASE on
        // entity_group forgoes the GiST index for these rows, fine at this scale.
        $periodRange = 'int4range('
            ."CASE WHEN entities.entity_group = 'EVENT' THEN geometry_periods.start_year - 10 ELSE geometry_periods.start_year END, "
            ."CASE WHEN entities.entity_group = 'EVENT' THEN COALESCE(geometry_periods.end_year, geometry_periods.start_year) + 11 "
            ."WHEN geometry_periods.end_year IS NULL THEN NULL ELSE geometry_periods.end_year + 1 END, '[)')";
        if (isset($filters['temporal_start'], $filters['temporal_end'])) {
            $start = (int) $filters['temporal_start'];
            $end = (int) $filters['temporal_end'];
            $query->whereRaw("{$periodRange} && int4range(?::integer, ?::integer + 1, '[)')", [$start, $end]);
        } else {
            $year = (int) $filters['year'];
            $query->whereRaw("{$periodRange} @> ?::integer", [$year]);
        }

        // Spatial bbox on the SAME COALESCE geometry that is serialized (MQ-9), so
        // the filter and the rendered geometry agree; uses gp_map_geom_gist. The
        // longitudes are normalized and, when the viewport crosses the antimeridian
        // (min_lng > max_lng), the filter ORs two envelopes (MQ-17).
        $w = $this->normalizeLng((float) $filters['bbox_min_lng']);
        $s = (float) $filters['bbox_min_lat'];
        $e = $this->normalizeLng((float) $filters['bbox_max_lng']);
        $n = (float) $filters['bbox_max_lat'];
        $geomCol = 'COALESCE(geometry_periods.territory_geom, geometry_periods.geom)';

        if ($w <= $e) {
            $query->whereRaw("{$geomCol} && ST_MakeEnvelope(?, ?, ?, ?, 4326)", [$w, $s, $e, $n]);
        } else {
            $query->where(function ($q) use ($geomCol, $w, $s, $e, $n): void {
                $q->whereRaw("{$geomCol} && ST_MakeEnvelope(?, ?, 180, ?, 4326)", [$w, $s, $n])
                    ->orWhereRaw("{$geomCol} && ST_MakeEnvelope(-180, ?, ?, ?, 4326)", [$s, $e, $n]);
            });
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

            $deduped = DB::query()->fromSub($query, 'm');

            if ($backfill) {
                // Rank the (unthresholded) deduped rows by impact, then keep those
                // above the threshold OR within the floor — so the map always shows
                // the top `floor` highest-impact entities in view, and everything
                // above the threshold when there is more than that.
                $ranked = DB::query()
                    ->fromSub($deduped, 'd')
                    ->selectRaw('d.*, ROW_NUMBER() OVER (ORDER BY d.impact_score DESC NULLS LAST) AS impact_rank');

                $rows = DB::query()
                    ->fromSub($ranked, 'r')
                    ->whereRaw('(r.impact_score >= ? OR r.impact_rank <= ?)', [$minImpact, $floor])
                    ->orderByRaw('r.display_priority DESC NULLS LAST, r.impact_score DESC NULLS LAST')
                    ->limit($limit)
                    ->cursor();
            } else {
                // Re-order the deduped rows by display priority then impact (MQ-15).
                $rows = $deduped
                    ->orderByRaw('m.display_priority DESC NULLS LAST, m.impact_score DESC NULLS LAST')
                    ->limit($limit)
                    ->cursor();
            }
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

    /** Wrap an out-of-range longitude into [-180, 180]; in-range values (incl. ±180) are unchanged. */
    private function normalizeLng(float $lng): float
    {
        if ($lng >= -180.0 && $lng <= 180.0) {
            return $lng;
        }

        $wrapped = fmod($lng + 180.0, 360.0);
        if ($wrapped < 0) {
            $wrapped += 360.0;
        }

        return $wrapped - 180.0;
    }
}
