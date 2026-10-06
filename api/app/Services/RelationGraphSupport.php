<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\Entity;
use Illuminate\Support\Collection;

/**
 * Shared helpers for the relation-graph endpoints (entity + chronicle).
 *
 * Both endpoints return the same node and edge shapes; edge rows come from
 * set-based SQL over `relationships` and nodes are hydrated in one query.
 */
final class RelationGraphSupport
{
    /** Columns every edge query must select (rows are stdClass). */
    public const EDGE_COLUMNS = 'r.relationship_id, r.source_entity_id, r.target_entity_id, r.relationship_type::text AS relationship_type, r.start_year, r.end_year, r.description, r.confidence::text AS confidence';

    /**
     * `confidence_level` is a Postgres enum declared high < medium < low < unresolved,
     * so ascending enum order is "most confident first" (NULLs last).
     */
    public const ORDER_CONFIDENCE = 'r.confidence ASC NULLS LAST';

    /**
     * Encode a list of uuids as a Postgres array literal for `?::uuid[]` bindings.
     *
     * @param  iterable<string>  $ids
     */
    public static function pgArray(iterable $ids): string
    {
        $out = [];
        foreach ($ids as $id) {
            $out[] = $id;
        }

        return '{'.implode(',', $out).'}';
    }

    /**
     * @param  list<string>  $values
     */
    public static function pgTextArray(array $values): string
    {
        return '{'.implode(',', array_map(fn (string $v): string => '"'.str_replace(['\\', '"'], ['\\\\', '\\"'], $v).'"', $values)).'}';
    }

    /**
     * Hydrate node payloads (without `depth`) for the given entity ids.
     *
     * @param  list<string>  $ids
     * @return Collection<string, array<string, mixed>> keyed by entity id
     */
    public static function nodes(array $ids): Collection
    {
        if ($ids === []) {
            return collect();
        }

        return Entity::query()
            ->selectForGraph()
            ->whereIn('entities.entity_id', $ids)
            ->get()
            ->mapWithKeys(fn (Entity $e): array => [$e->entity_id => [
                'id' => $e->entity_id,
                'name' => $e->name,
                'entity_type' => $e->entity_type?->value,
                'entity_group' => $e->entity_group?->value,
                'start_year' => $e->start_year !== null ? (int) $e->start_year : null,
                'end_year' => $e->end_year !== null ? (int) $e->end_year : null,
                'impact_score' => $e->impact_score,
            ]]);
    }

    /**
     * @return array<string, mixed>
     */
    public static function edge(object $row): array
    {
        return [
            'id' => $row->relationship_id,
            'source' => $row->source_entity_id,
            'target' => $row->target_entity_id,
            'relationship_type' => $row->relationship_type,
            'start_year' => $row->start_year !== null ? (int) $row->start_year : null,
            'end_year' => $row->end_year !== null ? (int) $row->end_year : null,
            'description' => $row->description,
            'confidence' => $row->confidence,
        ];
    }
}
