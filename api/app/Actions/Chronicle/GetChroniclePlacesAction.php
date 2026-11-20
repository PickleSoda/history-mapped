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
 *   - `reaches`: for a thing that spreads (a disease, a religion, a crop, a
 *     technology), the chronicle's other entities it is recorded as reaching:
 *     the targets of its `spread_to` links, the sources of `adopted` links to
 *     it ("Japan adopted Buddhism"), and, once it has either, the places it
 *     is `located_at`. A step has one primary relationship, so "the second
 *     wave struck Brest, Freetown and Boston" keeps only one of its three
 *     links there; these are the others, for the player to draw the spread
 *     from what is recorded. Each comes with the year the link starts (null
 *     when it has none): the same two entities can meet again in a step a
 *     century later. Empty for everything else.
 *
 * Entities with none of the three are left out.
 */
class GetChroniclePlacesAction
{
    /** Five decimals: about a metre, plenty for a map point. */
    private const PRECISION = 5;

    /**
     * @return list<array{id: string, group: string|null, at: array{0: float, 1: float}|null, borders: list<array{id: int, from: int|null, to: int|null, primary: bool}>, reaches: list<array{id: string, year: int|null}>}>
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
            reached AS (
                -- "X spread_to Y": X reached Y. "Y adopted X": X reached Y.
                SELECT r.source_entity_id AS carrier, r.target_entity_id AS entity_id, r.start_year AS year
                FROM relationships r
                WHERE r.relationship_type = 'spread_to'
                  AND r.source_entity_id IN (SELECT entity_id FROM ids)
                  AND r.target_entity_id IN (SELECT entity_id FROM ids)
                UNION
                SELECT r.target_entity_id, r.source_entity_id, r.start_year
                FROM relationships r
                WHERE r.relationship_type = 'adopted'
                  AND r.target_entity_id IN (SELECT entity_id FROM ids)
                  AND r.source_entity_id IN (SELECT entity_id FROM ids)
            ),
            seen AS (
                SELECT carrier, entity_id, year FROM reached
                UNION
                -- Where a thing that spreads is said to be ("the pandemic, located at Camp Funston").
                SELECT r.source_entity_id, r.target_entity_id, r.start_year
                FROM relationships r
                WHERE r.relationship_type = 'located_at'
                  AND r.source_entity_id IN (SELECT carrier FROM reached)
                  AND r.target_entity_id IN (SELECT entity_id FROM ids)
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
                       AND COALESCE(egr.external_tags->>'type', '') <> 'chronology') AS borders,
                    (SELECT COALESCE(json_agg(json_build_object('id', s.entity_id, 'year', s.year)
                                ORDER BY s.entity_id, s.year), '[]'::json)
                     FROM seen s
                     WHERE s.carrier = e.entity_id AND s.entity_id <> e.entity_id) AS reaches
                FROM ids
                JOIN entities e ON e.entity_id = ids.entity_id
            )
            SELECT entity_id, entity_group, ST_X(pt) AS lng, ST_Y(pt) AS lat, borders, reaches
            FROM placed
            WHERE pt IS NOT NULL OR json_array_length(borders) > 0 OR json_array_length(reaches) > 0
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
            'reaches' => array_map(
                fn (array $r): array => ['id' => (string) $r['id'], 'year' => $r['year'] !== null ? (int) $r['year'] : null],
                json_decode((string) $row->reaches, true) ?: [],
            ),
        ], $rows);
    }
}
