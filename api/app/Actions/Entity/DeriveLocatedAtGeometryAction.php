<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\EntityGroup;
use App\Models\GeometryPeriod;
use App\Support\TimelineRebuild;
use Illuminate\Support\Facades\DB;

/**
 * Additive geometry backfill: place an entity that has no map geometry at the
 * point of the place it is `located_at`.
 *
 * The SPA map renders only `geometry_periods` rows (MapEntitiesAction). Campaign
 * entities without a Wikidata/OHM match (verification_status=needs_review) never
 * get one, because the import only copies the entity's OWN point into a period and
 * pipeline relations are bulk-inserted without derivation. Their `located_at`
 * edge (thing → place) is the best remaining location signal, so for each source
 * with no geometry period and no own point this writes ONE `presence` period
 * (provenance `derived`, keyed by that relationship) carrying the target's point.
 *
 * Safety: inserts only; skips any entity that already has a geometry period or a
 * primary point (re-checked at insert time); one row per relationship is enforced
 * by gp_unique_derived_presence_relationship_idx, so re-runs are no-ops. Targets
 * are PLACE entities or political_entity polities (never a person or group) with a
 * POINT (primary location first, else their own nearest-in-time period point),
 * preferring a PLACE target, and only while the target keeps a QID or an active
 * geo-ref (a point left behind by a cleared QID is not trusted). A PLACE source only ever takes a PLACE
 * target, never a polity centroid; `$preciseOnly` applies that to events too.
 * created_by is NOT one of the markers entity:backfill deletes.
 */
class DeriveLocatedAtGeometryAction
{
    public const CREATED_BY = 'derive:located_at';

    public const SUPPORTED_GROUPS = [EntityGroup::Event, EntityGroup::Place];

    /**
     * Candidate rows (one per source entity, best target first) plus skip counts.
     *
     * @param  list<EntityGroup>  $groups
     * @return array{candidates: list<object>, skipped: array<string, int>}
     */
    public function plan(array $groups, bool $preciseOnly = false, ?string $entityId = null): array
    {
        $groupValues = array_map(fn (EntityGroup $g): string => $g->value, $groups);
        $placeholders = implode(', ', array_fill(0, count($groupValues), '?'));
        $entityFilter = $entityId !== null ? 'AND e.entity_id = ?' : '';
        $bindings = [...$groupValues, ...($entityId !== null ? [$entityId] : [])];

        $sql = <<<SQL
            WITH src AS (
                SELECT e.entity_id, e.name, e.entity_type::text AS entity_type, e.entity_group::text AS entity_group,
                       COALESCE(tr.start_year, tr.end_year) AS e_start, tr.end_year AS e_end,
                       EXISTS (SELECT 1 FROM entity_locations l WHERE l.entity_id = e.entity_id AND l.is_primary
                               AND (l.geom IS NOT NULL OR l.territory_geom IS NOT NULL)) AS has_own_point
                FROM entities e
                LEFT JOIN entity_temporal_ranges tr ON tr.entity_id = e.entity_id AND tr.is_primary
                WHERE e.entity_group::text IN ({$placeholders}) {$entityFilter}
                  AND NOT EXISTS (SELECT 1 FROM geometry_periods gp WHERE gp.entity_id = e.entity_id)
            )
            SELECT DISTINCT ON (s.entity_id)
                   s.entity_id, s.name, s.entity_type, s.entity_group, s.e_start, s.e_end, s.has_own_point,
                   r.relationship_id, r.start_year AS r_start, r.end_year AS r_end, r.description AS r_description,
                   t.entity_id AS target_id, t.name AS target_name, t.entity_group::text AS target_group,
                   t.entity_type::text AS target_type, pt.point_source, ST_AsGeoJSON(pt.geom) AS geojson
            FROM src s
            JOIN relationships r ON r.source_entity_id = s.entity_id AND r.relationship_type = 'located_at'
            JOIN entities t ON t.entity_id = r.target_entity_id
                AND (t.entity_group::text = 'PLACE' OR t.entity_type::text = 'political_entity')
                -- The point must still be backed by an identity: a QID, or an active geo-ref.
                -- A QID cleared by a repair leaves its Wikidata point behind (Uch, Pakistan,
                -- still sits on Uchiko-chō, Japan); never spread such a residue point.
                AND (COALESCE(t.wikidata_id, '') <> ''
                     OR EXISTS (SELECT 1 FROM entity_geo_refs g WHERE g.entity_id = t.entity_id AND g.is_active))
            CROSS JOIN LATERAL (
                SELECT p.geom, p.point_source FROM (
                    SELECT l.geom, 'location' AS point_source, 0 AS rank, 0 AS dist
                    FROM entity_locations l
                    WHERE l.entity_id = t.entity_id AND l.is_primary AND GeometryType(l.geom) = 'POINT'
                    UNION ALL
                    SELECT g.geom, 'geometry_period', 1,
                           abs(g.start_year - COALESCE(s.e_start, r.start_year, r.end_year, g.start_year))
                    FROM geometry_periods g
                    WHERE g.entity_id = t.entity_id AND GeometryType(g.geom) = 'POINT'
                ) p
                ORDER BY p.rank, p.dist
                LIMIT 1
            ) pt
            WHERE (s.entity_group <> 'PLACE' OR t.entity_group::text = 'PLACE')
            ORDER BY s.entity_id, (t.entity_group::text = 'PLACE') DESC, pt.point_source = 'location' DESC,
                     r.created_at NULLS LAST, r.relationship_id
            SQL;

        $candidates = [];
        $skipped = ['own_point' => 0, 'no_year' => 0, 'polity_target' => 0];

        foreach (DB::select($sql, $bindings) as $row) {
            if ($row->has_own_point) {
                // Its own point needs entity:backfill (territory period), not a borrowed one.
                $skipped['own_point']++;

                continue;
            }

            if ($preciseOnly && $row->target_group !== EntityGroup::Place->value) {
                $skipped['polity_target']++;

                continue;
            }

            [$start, $end] = $this->years($row);

            if ($start === null) {
                $skipped['no_year']++;

                continue;
            }

            $row->start_year = $start;
            $row->end_year = $end;
            $row->confidence = $row->target_group === EntityGroup::Place->value ? 'medium' : 'low';
            $candidates[] = $row;
        }

        return ['candidates' => $candidates, 'skipped' => $skipped];
    }

    /**
     * Write the planned periods. Returns the number inserted.
     *
     * @param  list<object>  $candidates
     */
    public function apply(array $candidates): int
    {
        $inserted = 0;

        TimelineRebuild::withoutRebuilds(function () use ($candidates, &$inserted): void {
            foreach ($candidates as $row) {
                $inserted += DB::transaction(function () use ($row): int {
                    // Re-check at write time: strictly additive, never a second period.
                    $hasGeometry = GeometryPeriod::query()->where('entity_id', $row->entity_id)->exists()
                        || DB::table('entity_locations')
                            ->where('entity_id', $row->entity_id)
                            ->where('is_primary', true)
                            ->where(fn ($q) => $q->whereNotNull('geom')->orWhereNotNull('territory_geom'))
                            ->exists();

                    if ($hasGeometry) {
                        return 0;
                    }

                    GeometryPeriod::query()->create([
                        'entity_id' => $row->entity_id,
                        'period_type' => 'presence',
                        'start_year' => $row->start_year,
                        'end_year' => $row->end_year,
                        'geom' => json_decode($row->geojson, true),
                        'description' => $row->r_description,
                        'provenance_mode' => 'derived',
                        'relationship_id' => $row->relationship_id,
                        'confidence' => $row->confidence,
                        'created_by' => self::CREATED_BY,
                    ]);

                    return 1;
                });
            }
        });

        return $inserted;
    }

    /**
     * The entity's own primary range, else the located_at relation's years. An
     * event is momentary (open end → end = start); a place keeps an open end.
     *
     * @return array{0: int|null, 1: int|null}
     */
    private function years(object $row): array
    {
        if ($row->e_start !== null) {
            [$start, $end] = [(int) $row->e_start, $row->e_end !== null ? (int) $row->e_end : null];
        } else {
            $start = $row->r_start ?? $row->r_end;
            $start = $start !== null ? (int) $start : null;
            $end = $row->r_end !== null ? (int) $row->r_end : null;
        }

        if ($start === null) {
            return [null, null];
        }

        if ($row->entity_group === EntityGroup::Event->value) {
            $end ??= $start;
        }

        if ($end !== null && $end < $start) {
            $end = $row->entity_group === EntityGroup::Event->value ? $start : null;
        }

        return [$start, $end];
    }
}
