<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use Illuminate\Support\Facades\DB;

/**
 * Where a chronicle's entities sit on the map, for the atlas player's step
 * layer (lines, highlighted borders, the trail of earlier steps).
 *
 * The entity set is every entry's entities plus both ends of each entry's
 * primary relationship. Each placed entity gets:
 *
 *   - `at`: its map point, [lng, lat]. The primary location's point, else the
 *     earliest geometry period's (the tiles draw these, so a line ends on the
 *     marker the reader sees).
 *   - `borders`: its OpenHistoricalMap boundaries, each with the years it
 *     stands for: OHM draws a polity's every change of border as its own
 *     relation, so the player outlines the ones covering a step's year. The
 *     same links the map stories outline (ResolveMapStoryAction::ohmBoundaries):
 *     active relations and ways, not rejected, no `chronology` relation;
 *     primary first, then by match score. `id` is OHM's signed `osm_id`
 *     (negative: a relation).
 *
 * Entities with neither are left out.
 */
class GetChroniclePlacesAction
{
    /** Five decimals: about a metre, plenty for a map point. */
    private const PRECISION = 5;

    /**
     * @return list<array{id: string, group: string|null, at: array{0: float, 1: float}|null, borders: list<array{id: int, from: int|null, to: int|null, primary: bool}>}>
     */
    public function __invoke(Chronicle $chronicle): array
    {
        $rows = DB::select(
            <<<'SQL'
            WITH ids AS (
                SELECT cee.entity_id
                FROM chronicle_entry_entities cee
                JOIN chronicle_entries ce ON ce.entry_id = cee.entry_id
                WHERE ce.chronicle_id = :c1
                UNION
                SELECT unnest(ARRAY[r.source_entity_id, r.target_entity_id])
                FROM chronicle_entries ce
                JOIN relationships r ON r.relationship_id = ce.primary_relationship_id
                WHERE ce.chronicle_id = :c2
            ),
            placed AS (
                SELECT e.entity_id, e.entity_group::text AS entity_group,
                    ST_PointOnSurface(COALESCE(
                        (SELECT el.geom FROM entity_locations el
                         WHERE el.entity_id = e.entity_id AND el.is_primary = true AND el.geom IS NOT NULL
                         ORDER BY el.updated_at DESC NULLS LAST, el.created_at DESC NULLS LAST
                         LIMIT 1),
                        (SELECT COALESCE(gp.geom, gp.territory_geom) FROM geometry_periods gp
                         WHERE gp.entity_id = e.entity_id
                         ORDER BY gp.start_year, gp.geometry_period_id
                         LIMIT 1)
                    )) AS pt,
                    (SELECT COALESCE(json_agg(json_build_object(
                                'id', tiles.signed_osm_id(egr.external_type::text, egr.external_id),
                                'from', egr.temporal_start_year,
                                'to', egr.temporal_end_year,
                                'primary', egr.match_role = 'primary'
                            ) ORDER BY (egr.match_role = 'primary') DESC, egr.match_score DESC NULLS LAST,
                                egr.external_type, egr.external_id), '[]'::json)
                     FROM entity_geo_refs egr
                     WHERE egr.entity_id = e.entity_id AND egr.provider = 'ohm' AND egr.is_active = true
                       AND egr.external_type IN ('relation', 'way') AND egr.match_role <> 'rejected'
                       AND COALESCE(egr.external_tags->>'type', '') <> 'chronology') AS borders
                FROM ids
                JOIN entities e ON e.entity_id = ids.entity_id
            )
            SELECT entity_id, entity_group, ST_X(pt) AS lng, ST_Y(pt) AS lat, borders
            FROM placed
            WHERE pt IS NOT NULL OR json_array_length(borders) > 0
            ORDER BY entity_id
            SQL,
            ['c1' => $chronicle->chronicle_id, 'c2' => $chronicle->chronicle_id],
        );

        return array_map(fn (object $row): array => [
            'id' => (string) $row->entity_id,
            'group' => $row->entity_group !== null ? strtolower((string) $row->entity_group) : null,
            'at' => $row->lng !== null && $row->lat !== null
                ? [round((float) $row->lng, self::PRECISION), round((float) $row->lat, self::PRECISION)]
                : null,
            'borders' => array_values(array_filter(array_map(
                fn (array $b): ?array => $b['id'] === null ? null : [
                    'id' => (int) $b['id'],
                    'from' => $b['from'] !== null ? (int) $b['from'] : null,
                    'to' => $b['to'] !== null ? (int) $b['to'] : null,
                    'primary' => (bool) $b['primary'],
                ],
                json_decode((string) $row->borders, true) ?: [],
            ))),
        ], $rows);
    }
}
