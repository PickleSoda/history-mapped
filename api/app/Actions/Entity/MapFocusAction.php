<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Actions\Graph\GetEntityGraphAction;
use App\Builders\EntityBuilder;
use App\Services\RelationGraphSupport as G;
use Illuminate\Support\Facades\DB;

/**
 * The map points of a focused set of entities, wherever and whenever they are:
 * either one entity with its relations one or two hops out, or the best
 * matches of a name search. The viewport query (MapEntitiesAction) shows what
 * is prominent at a year in the visible area; this one ignores the year, the
 * area and the zoom's impact threshold, so the whole set shows at any zoom.
 *
 * One point per entity: its primary location, else a point on its newest
 * geometry period. Entities without either are left out.
 */
class MapFocusAction
{
    public const DEFAULT_LIMIT = 300;

    public const MAX_LIMIT = 500;

    /** A search with fewer plain matches than this also tries typo-tolerant ones. */
    private const FUZZY_BELOW = 5;

    public function __construct(private readonly GetEntityGraphAction $graph) {}

    /**
     * @param  array{related_to?: string, depth?: int, search?: string, groups?: list<string>, limit?: int}  $filters
     * @return list<array{id: string, geometry_json: string, properties: array<string, mixed>}>
     */
    public function __invoke(array $filters): array
    {
        $limit = min(self::MAX_LIMIT, max(1, (int) ($filters['limit'] ?? self::DEFAULT_LIMIT)));
        $groups = $filters['groups'] ?? [];

        // Entity id => rank: hops from the root, or the position in the search.
        $ranks = isset($filters['related_to'])
            ? $this->relatedTo($filters['related_to'], (int) ($filters['depth'] ?? 2), $groups, $limit)
            : $this->matching((string) $filters['search'], $groups, $limit);

        if ($ranks === []) {
            return [];
        }

        $ohmWhere = "egr.entity_id = e.entity_id AND egr.provider = 'ohm' AND egr.is_active = true";
        $ohmOrder = "ORDER BY (egr.match_role = 'primary') DESC, egr.updated_at DESC NULLS LAST LIMIT 1";

        $rows = DB::select(
            <<<SQL
            SELECT e.entity_id, e.entity_type, e.entity_group, e.impact_score,
                COALESCE(
                    (SELECT a.name FROM entity_aliases a
                      WHERE a.entity_id = e.entity_id AND a.is_primary = true
                      ORDER BY a.updated_at DESC NULLS LAST, a.created_at DESC NULLS LAST LIMIT 1),
                    e.name
                ) AS display_name,
                EXISTS (SELECT 1 FROM map_stories ms WHERE ms.entity_id = e.entity_id) AS has_map_story,
                (SELECT egr.external_id FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder}) AS ohm_external_id,
                (SELECT egr.external_type::text FROM entity_geo_refs egr WHERE {$ohmWhere} {$ohmOrder}) AS ohm_external_type,
                ST_AsGeoJSON(pt.geom, 5)::text AS geojson
            FROM entities e
            CROSS JOIN LATERAL (
                SELECT COALESCE(
                    (SELECT ST_PointOnSurface(el.geom) FROM entity_locations el
                      WHERE el.entity_id = e.entity_id AND el.is_primary = true AND el.geom IS NOT NULL LIMIT 1),
                    (SELECT ST_PointOnSurface(COALESCE(gp.geom, gp.territory_geom)) FROM geometry_periods gp
                      WHERE gp.entity_id = e.entity_id AND COALESCE(gp.geom, gp.territory_geom) IS NOT NULL
                      ORDER BY gp.start_year DESC NULLS LAST LIMIT 1)
                ) AS geom
            ) pt
            WHERE e.entity_id = ANY(?::uuid[]) AND pt.geom IS NOT NULL
            SQL,
            [G::pgArray(array_keys($ranks))],
        );

        usort($rows, fn (object $a, object $b): int => $ranks[$a->entity_id] <=> $ranks[$b->entity_id]
            ?: ($b->impact_score ?? 0) <=> ($a->impact_score ?? 0));

        $related = isset($filters['related_to']);

        return array_map(fn (object $row): array => [
            'id' => $row->entity_id,
            'geometry_json' => $row->geojson,
            'properties' => [
                'id' => $row->entity_id,
                'name' => $row->display_name,
                'entity_type' => $row->entity_type,
                'entity_group' => $row->entity_group,
                'impact_score' => $row->impact_score,
                'has_map_story' => (bool) $row->has_map_story,
                'ohm_provider' => $row->ohm_external_id !== null ? 'ohm' : null,
                'ohm_external_type' => $row->ohm_external_type,
                'ohm_external_id' => $row->ohm_external_id,
                // Hops from the focused entity (0 = itself); 0 for search matches.
                'depth' => $related ? $ranks[$row->entity_id] : 0,
            ],
        ], array_slice($rows, 0, $limit));
    }

    /**
     * The entity and its neighbours, id => hops.
     *
     * @param  list<string>  $groups
     * @return array<string, int>
     */
    private function relatedTo(string $rootId, int $depth, array $groups, int $limit): array
    {
        // Edge rows carry lowercase ids; an uppercase root would not match itself.
        $graph = ($this->graph)(strtolower($rootId), ['depth' => $depth, 'groups' => $groups, 'limit' => $limit]);

        $ranks = [];
        foreach ($graph['nodes'] as $node) {
            $ranks[$node['id']] = (int) $node['depth'];
        }

        return $ranks;
    }

    /**
     * The most prominent placed entities whose name matches, id => position.
     * (The list's relevance order puts short exact names first, and those are
     * mostly people, who have no place on the map.)
     *
     * @param  list<string>  $groups
     * @return array<string, int>
     */
    private function matching(string $search, array $groups, int $limit): array
    {
        $search = trim($search);
        $short = mb_strlen($search) < EntityBuilder::SEARCH_PREFIX_BELOW;
        $plain = "name ILIKE ? OR to_tsvector('english', name) @@ plainto_tsquery('english', ?)";
        $plainBindings = ['%'.$search.'%', $search];

        // The names are matched first, in the narrow `entity_names` table and
        // on their own (MATERIALIZED): left to itself the planner walks every
        // entity in impact order and tests each name (1.4 s for "william").
        $placed = function (string $match, array $bindings) use ($groups, $limit): array {
            $groupSql = $groups === [] ? '' : 'AND e.entity_group::text = ANY(?::text[])';
            if ($groups !== []) {
                $bindings[] = G::pgTextArray($groups);
            }
            $bindings[] = $limit;

            return array_column(DB::select(
                <<<SQL
                WITH matches AS MATERIALIZED ({$match})
                SELECT e.entity_id
                FROM matches
                JOIN entities e ON e.entity_id = matches.entity_id
                -- The primary point only: checking geometry periods as well made
                -- common words four times slower. Entities placed by a period
                -- alone were given a primary point (migration 2026_11_20_110000).
                WHERE EXISTS (
                    SELECT 1 FROM entity_locations el
                    WHERE el.entity_id = e.entity_id AND el.is_primary = true AND el.geom IS NOT NULL
                ) {$groupSql}
                ORDER BY e.impact_score DESC NULLS LAST, e.entity_id
                LIMIT ?
                SQL,
                $bindings,
            ), 'entity_id');
        };

        if ($short) {
            // One or two letters: a name prefix (trigrams need three characters).
            $ids = $placed(
                'SELECT entity_id FROM entities WHERE lower(name) LIKE ?',
                [addcslashes(mb_strtolower($search), '\\%_').'%'],
            );
        } else {
            $ids = $placed("SELECT entity_id FROM entity_names WHERE {$plain}", $plainBindings);
            // Typo-tolerant matching rechecks tens of thousands of names for a
            // common word, so it runs only when the plain match finds almost nothing.
            if (count($ids) < self::FUZZY_BELOW && mb_strlen($search) >= EntityBuilder::SEARCH_FUZZY_FROM) {
                $ids = $placed(
                    "SELECT entity_id FROM entity_names WHERE {$plain} OR name % ?",
                    [...$plainBindings, $search],
                );
            }
        }

        $ranks = array_flip($ids);

        return $ranks;
    }
}
