<?php

declare(strict_types=1);

namespace App\Actions\Graph;

use App\Models\Chronicle;
use App\Services\RelationGraphSupport as G;
use Illuminate\Support\Facades\DB;

/**
 * Whole-chronicle graph: the chronicle's entity set, the relations among them
 * (and optionally to the outside), plus per-step membership.
 *
 * Chronicle entity set = pivot entities of every entry + both ends of each
 * entry's primary relationship. Primary relationships are always included
 * (scope "primary") even when `relationship_types` would otherwise drop them,
 * so every step's `primary_relationship_id` resolves to an edge.
 */
class GetChronicleGraphAction
{
    public const DEFAULT_EXTERNAL_LIMIT = 12;

    /**
     * @param  array{external?: bool, external_limit?: int, relationship_types?: list<string>}  $filters
     * @return array<string, mixed>
     */
    public function __invoke(Chronicle $chronicle, array $filters = []): array
    {
        $external = (bool) ($filters['external'] ?? true);
        $externalLimit = (int) ($filters['external_limit'] ?? self::DEFAULT_EXTERNAL_LIMIT);

        $entries = DB::select(
            'SELECT entry_id, sequence_order, start_year, end_year, primary_relationship_id
             FROM chronicle_entries WHERE chronicle_id = ? ORDER BY sequence_order, entry_id',
            [$chronicle->chronicle_id],
        );

        $entryIds = array_map(fn ($e) => $e->entry_id, $entries);
        $primaryIds = array_values(array_unique(array_filter(array_map(fn ($e) => $e->primary_relationship_id, $entries))));

        // Step entity membership: pivot entities...
        $stepEntities = array_fill_keys($entryIds, []);
        if ($entryIds !== []) {
            $pivot = DB::select(
                'SELECT entry_id, entity_id FROM chronicle_entry_entities WHERE entry_id = ANY(?::uuid[])',
                [G::pgArray($entryIds)],
            );
            foreach ($pivot as $p) {
                $stepEntities[$p->entry_id][$p->entity_id] = true;
            }
        }

        // ...plus both ends of the primary relationship.
        $primaryRows = [];
        if ($primaryIds !== []) {
            $rows = DB::select(
                'SELECT '.G::EDGE_COLUMNS.' FROM relationships r WHERE r.relationship_id = ANY(?::uuid[])',
                [G::pgArray($primaryIds)],
            );
            foreach ($rows as $row) {
                $primaryRows[$row->relationship_id] = $row;
            }
        }
        foreach ($entries as $e) {
            $primary = $primaryRows[$e->primary_relationship_id] ?? null;
            if ($primary !== null) {
                $stepEntities[$e->entry_id][$primary->source_entity_id] = true;
                $stepEntities[$e->entry_id][$primary->target_entity_id] = true;
            }
        }

        $set = [];
        foreach ($stepEntities as $ids) {
            foreach ($ids as $id => $_) {
                $set[$id] = true;
            }
        }
        $setIds = array_keys($set);

        // Edges. Primary first, then the rest of the internal edges, then external.
        $edges = [];
        foreach ($primaryRows as $id => $row) {
            $edges[$id] = ['row' => $row, 'scope' => 'primary'];
        }
        foreach ($this->internalEdges($setIds, $filters['relationship_types'] ?? []) as $row) {
            $edges[$row->relationship_id] ??= ['row' => $row, 'scope' => 'internal'];
        }
        $externalIds = [];
        if ($external && $externalLimit > 0 && $setIds !== []) {
            foreach ($this->externalEdges($setIds, $externalLimit, $filters['relationship_types'] ?? []) as $row) {
                $edges[$row->relationship_id] ??= ['row' => $row, 'scope' => 'external'];
                foreach ([$row->source_entity_id, $row->target_entity_id] as $end) {
                    if (! isset($set[$end])) {
                        $externalIds[$end] = true;
                    }
                }
            }
        }

        // Step membership.
        $entityToSteps = [];
        $stepsOut = [];
        $edgeSteps = [];
        foreach ($entries as $e) {
            $ids = array_keys($stepEntities[$e->entry_id]);
            foreach ($ids as $id) {
                $entityToSteps[$id][] = (int) $e->sequence_order;
            }
            $stepsOut[$e->entry_id] = [
                'entry_id' => $e->entry_id,
                'sequence_order' => (int) $e->sequence_order,
                'start_year' => $e->start_year !== null ? (int) $e->start_year : null,
                'end_year' => $e->end_year !== null ? (int) $e->end_year : null,
                'primary_relationship_id' => $e->primary_relationship_id,
                'entity_ids' => $ids,
                'relationship_ids' => isset($primaryRows[$e->primary_relationship_id]) ? [$e->primary_relationship_id] : [],
            ];
        }
        $entryBySeq = [];
        foreach ($entries as $e) {
            $entryBySeq[(int) $e->sequence_order][] = $e->entry_id;
        }

        foreach ($edges as $id => $edge) {
            if ($edge['scope'] === 'external') {
                continue;
            }
            $row = $edge['row'];
            $src = $entityToSteps[$row->source_entity_id] ?? [];
            $both = array_values(array_intersect($src, $entityToSteps[$row->target_entity_id] ?? []));
            // Map sequence_order -> entries (sequence_order is normally unique per chronicle).
            foreach ($both as $seq) {
                foreach ($entryBySeq[$seq] as $entryId) {
                    if (isset($stepEntities[$entryId][$row->source_entity_id], $stepEntities[$entryId][$row->target_entity_id])
                        && ! in_array($id, $stepsOut[$entryId]['relationship_ids'], true)) {
                        $stepsOut[$entryId]['relationship_ids'][] = $id;
                    }
                }
                $edgeSteps[$id][] = $seq;
            }
        }

        $nodes = G::nodes(array_merge($setIds, array_keys($externalIds)));
        $nodeOut = [];
        foreach ($nodes as $id => $node) {
            $inChronicle = isset($set[$id]);
            $steps = array_values(array_unique($entityToSteps[$id] ?? []));
            sort($steps);
            $nodeOut[] = $node + [
                'depth' => $inChronicle ? 0 : 1,
                'in_chronicle' => $inChronicle,
                'steps' => $steps,
            ];
        }

        $edgeOut = [];
        foreach ($edges as $id => $edge) {
            $steps = array_values(array_unique($edgeSteps[$id] ?? []));
            sort($steps);
            // Drop edges whose ends no longer exist as nodes (defensive).
            if (! $nodes->has($edge['row']->source_entity_id) || ! $nodes->has($edge['row']->target_entity_id)) {
                continue;
            }
            $edgeOut[] = G::edge($edge['row']) + ['scope' => $edge['scope'], 'steps' => $steps];
        }

        return [
            'chronicle_id' => $chronicle->chronicle_id,
            'slug' => $chronicle->slug,
            'nodes' => $nodeOut,
            'edges' => $edgeOut,
            'steps' => array_values($stepsOut),
        ];
    }

    /**
     * @param  list<string>  $setIds
     * @param  list<string>  $types
     * @return list<object>
     */
    private function internalEdges(array $setIds, array $types): array
    {
        if ($setIds === []) {
            return [];
        }
        $arr = G::pgArray($setIds);
        $sql = 'SELECT '.G::EDGE_COLUMNS.' FROM relationships r
            WHERE r.source_entity_id = ANY(?::uuid[]) AND r.target_entity_id = ANY(?::uuid[])';
        $bindings = [$arr, $arr];
        if ($types !== []) {
            $sql .= ' AND r.relationship_type::text = ANY(?::text[])';
            $bindings[] = G::pgTextArray($types);
        }

        return DB::select($sql, $bindings);
    }

    /**
     * Top `$perEntity` edges per chronicle entity to entities outside the set.
     *
     * @param  list<string>  $setIds
     * @param  list<string>  $types
     * @return list<object>
     */
    private function externalEdges(array $setIds, int $perEntity, array $types): array
    {
        $arr = G::pgArray($setIds);
        $typeSql = '';
        $typeBindings = [];
        if ($types !== []) {
            $typeSql = ' AND r.relationship_type::text = ANY(?::text[])';
            $typeBindings = [G::pgTextArray($types)];
        }

        $sql = 'SELECT '.str_replace('r.', 'x.', G::EDGE_COLUMNS).' FROM (
                SELECT r.*, ROW_NUMBER() OVER (
                    PARTITION BY a.anchor
                    ORDER BY '.G::ORDER_CONFIDENCE.', o.impact_score DESC NULLS LAST, r.relationship_id
                ) AS rn
                FROM (
                    SELECT relationship_id, source_entity_id AS anchor, target_entity_id AS other FROM relationships
                      WHERE source_entity_id = ANY(?::uuid[]) AND target_entity_id <> ALL(?::uuid[])
                    UNION ALL
                    SELECT relationship_id, target_entity_id, source_entity_id FROM relationships
                      WHERE target_entity_id = ANY(?::uuid[]) AND source_entity_id <> ALL(?::uuid[])
                ) a
                JOIN relationships r ON r.relationship_id = a.relationship_id
                JOIN entities o ON o.entity_id = a.other
                WHERE TRUE'.$typeSql.'
            ) x WHERE x.rn <= ?';

        return DB::select($sql, [$arr, $arr, $arr, $arr, ...$typeBindings, $perEntity]);
    }
}
