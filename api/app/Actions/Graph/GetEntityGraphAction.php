<?php

declare(strict_types=1);

namespace App\Actions\Graph;

use App\Services\RelationGraphSupport as G;
use Illuminate\Support\Facades\DB;

/**
 * Relation neighbourhood of one entity, 1 or 2 hops out, bounded by `limit` edges.
 *
 * One set-based query per hop. Hop 2 starts from the (already limited) hop-1 nodes
 * and only spends whatever edge budget hop 1 left.
 */
class GetEntityGraphAction
{
    public const DEFAULT_LIMIT = 300;

    public const MAX_LIMIT = 1000;

    /**
     * @param  array{depth?: int, relationship_types?: list<string>, groups?: list<string>, from?: int|null, to?: int|null, limit?: int}  $filters
     * @return array{root: string, nodes: list<array<string, mixed>>, edges: list<array<string, mixed>>, truncated: bool}
     */
    public function __invoke(string $rootId, array $filters = []): array
    {
        $depth = (int) ($filters['depth'] ?? 1);
        $limit = min(self::MAX_LIMIT, max(1, (int) ($filters['limit'] ?? self::DEFAULT_LIMIT)));

        $depthOf = [$rootId => 0];
        $edges = [];
        $truncated = false;

        // Hop 1: edges touching the root.
        $rows = $this->hop([$rootId], [$rootId], $rootId, false, $filters, $limit + 1);
        if (count($rows) > $limit) {
            $truncated = true;
            $rows = array_slice($rows, 0, $limit);
        }
        foreach ($rows as $row) {
            $edges[$row->relationship_id] = $row;
            foreach ([$row->source_entity_id, $row->target_entity_id] as $end) {
                $depthOf[$end] ??= 1;
            }
        }

        // Hop 2: edges touching a depth-1 node, within the remaining budget.
        if ($depth >= 2 && ! $truncated) {
            $frontier = array_keys(array_filter($depthOf, fn (int $d): bool => $d === 1));
            $remaining = $limit - count($edges);
            if ($frontier !== [] && $remaining > 0) {
                $rows = $this->hop($frontier, array_keys($depthOf), $rootId, true, $filters, $remaining + 1);
                if (count($rows) > $remaining) {
                    $truncated = true;
                    $rows = array_slice($rows, 0, $remaining);
                }
                foreach ($rows as $row) {
                    $edges[$row->relationship_id] = $row;
                    foreach ([$row->source_entity_id, $row->target_entity_id] as $end) {
                        $depthOf[$end] ??= 2;
                    }
                }
            }
        }

        $nodes = G::nodes(array_keys($depthOf));
        $nodeList = [];
        foreach ($depthOf as $id => $d) {
            if ($nodes->has($id)) {
                $nodeList[] = $nodes[$id] + ['depth' => $d];
            }
        }

        return [
            'root' => $rootId,
            'nodes' => $nodeList,
            'edges' => array_values(array_map(G::edge(...), $edges)),
            'truncated' => $truncated,
        ];
    }

    /**
     * Edges touching `$frontier`. Ends outside `$known` must pass the group filter.
     * With `$skipRoot`, edges at the root are excluded (they were all taken in hop 1).
     *
     * @param  list<string>  $frontier
     * @param  list<string>  $known
     * @param  array<string, mixed>  $filters
     * @return list<object>
     */
    private function hop(array $frontier, array $known, string $rootId, bool $skipRoot, array $filters, int $take): array
    {
        $where = ['(r.source_entity_id = ANY(?::uuid[]) OR r.target_entity_id = ANY(?::uuid[]))'];
        $bindings = [G::pgArray($frontier), G::pgArray($frontier)];

        if ($skipRoot) {
            $where[] = 'r.source_entity_id <> ? AND r.target_entity_id <> ?';
            array_push($bindings, $rootId, $rootId);
        }

        if (! empty($filters['relationship_types'])) {
            $where[] = 'r.relationship_type::text = ANY(?::text[])';
            $bindings[] = G::pgTextArray($filters['relationship_types']);
        }

        if (! empty($filters['groups'])) {
            $groups = G::pgTextArray($filters['groups']);
            $knownArr = G::pgArray($known);
            $where[] = '(s.entity_id = ANY(?::uuid[]) OR s.entity_group::text = ANY(?::text[]))';
            $where[] = '(t.entity_id = ANY(?::uuid[]) OR t.entity_group::text = ANY(?::text[]))';
            array_push($bindings, $knownArr, $groups, $knownArr, $groups);
        }

        if (isset($filters['to'])) {
            $where[] = '(r.start_year IS NULL OR r.start_year <= ?)';
            $bindings[] = (int) $filters['to'];
        }
        if (isset($filters['from'])) {
            $where[] = '(r.end_year IS NULL OR r.end_year >= ?)';
            $bindings[] = (int) $filters['from'];
        }

        $frontierArr = G::pgArray($frontier);
        $sql = 'SELECT '.G::EDGE_COLUMNS.'
            FROM relationships r
            JOIN entities s ON s.entity_id = r.source_entity_id
            JOIN entities t ON t.entity_id = r.target_entity_id
            WHERE '.implode(' AND ', $where).'
            ORDER BY '.G::ORDER_CONFIDENCE.',
                CASE WHEN r.source_entity_id = ANY(?::uuid[]) THEN t.impact_score ELSE s.impact_score END DESC NULLS LAST,
                r.relationship_id
            LIMIT ?';
        $bindings[] = $frontierArr;
        $bindings[] = $take;

        return DB::select($sql, $bindings);
    }
}
