<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Scope;

use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Serializers\Serializers;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Query\Builder as QueryBuilder;
use Illuminate\Support\Facades\DB;

/**
 * Turns an ExportScope into one restricted query per record type, on top of each serializer's base
 * query. Every restriction is a `whereIn(<qualified column>, <subquery>)` over the entity set E and
 * chronicle set C, each built once. Slugs, types, groups, years and uuid lists are bound parameters
 * (a uuid list as one array parameter, so size never hits the bind limit). Types a scope leaves
 * empty get a builder that matches nothing.
 */
final class ScopeResolver
{
    /** @return array<string, Builder> keyed by RecordType value, in RecordType order */
    public function resolve(ExportScope $scope): array
    {
        $out = [];
        $chronicles = $scope->isAll() ? null : $this->chronicleSet($scope);
        $entities = $scope->isAll() ? null : $this->entitySet($scope, $chronicles);
        foreach (RecordType::cases() as $type) {
            $query = Serializers::for($type)->query();
            if (! $scope->isAll()) {
                $this->restrict($type, $query, $entities, $chronicles);
            }
            $out[$type->value] = $query;
        }

        return $out;
    }

    private function restrict(RecordType $type, Builder $query, ?QueryBuilder $entities, ?QueryBuilder $chronicles): void
    {
        match ($type) {
            RecordType::Entities => $this->within($query, 'entities.entity_id', $entities),
            RecordType::GeometryPeriods => $this->within($query, 'geometry_periods.entity_id', $entities),
            RecordType::GeoRefs => $this->within($query, 'entity_geo_refs.entity_id', $entities),
            RecordType::Chronicles => $this->within($query, 'chronicles.chronicle_id', $chronicles),
            RecordType::ChronicleEntries => $this->within($query, 'chronicle_entries.chronicle_id', $chronicles),
            RecordType::Relationships => $this->restrictRelationships($query, $entities, $chronicles),
        };
    }

    private function restrictRelationships(Builder $query, ?QueryBuilder $entities, ?QueryBuilder $chronicles): void
    {
        if ($entities === null && $chronicles === null) {
            $query->whereRaw('false');

            return;
        }

        $query->where(function (Builder $q) use ($entities, $chronicles) {
            if ($entities !== null) {
                $q->orWhere(fn (Builder $b) => $b
                    ->whereIn('relationships.source_entity_id', $entities)
                    ->whereIn('relationships.target_entity_id', $entities));
            }
            if ($chronicles !== null) {
                $q->orWhereIn('relationships.relationship_id', $this->primaryRelationships($chronicles));
            }
        });
    }

    private function within(Builder $query, string $column, ?QueryBuilder $set): void
    {
        $set === null ? $query->whereRaw('false') : $query->whereIn($column, $set);
    }

    /** Entity ids selected by the scope, or null when it selects none. */
    private function entitySet(ExportScope $scope, ?QueryBuilder $chronicles): ?QueryBuilder
    {
        $parts = [];

        if ($scope->entityIds() !== []) {
            $parts[] = $this->anyOf($this->entities(), 'entity_id', $scope->entityIds());
        }
        if ($scope->neighbourIds() !== []) {
            $ids = $scope->neighbourIds();
            $parts[] = $this->anyOf($this->entities(), 'entity_id', $ids);
            $parts[] = $this->anyOf(DB::table('relationships')->select('target_entity_id'), 'source_entity_id', $ids);
            $parts[] = $this->anyOf(DB::table('relationships')->select('source_entity_id'), 'target_entity_id', $ids);
        }
        if ($scope->types() !== []) {
            $parts[] = $this->entities()->whereIn('entity_type', $scope->types());
        }
        if ($scope->groups() !== []) {
            $parts[] = $this->entities()->whereIn('entity_group', $scope->groups());
        }
        foreach ($scope->yearRanges() as [$from, $to]) {
            // Overlap with the primary range; a null start is unknown (excluded), a null end is open.
            $parts[] = DB::table('entity_temporal_ranges')->select('entity_id')
                ->where('is_primary', true)
                ->whereNotNull('start_year')
                ->where('start_year', '<=', $to)
                ->where(fn ($q) => $q->whereNull('end_year')->orWhere('end_year', '>=', $from));
        }

        if ($chronicles !== null) {
            $entries = DB::table('chronicle_entries')->select('entry_id')->whereIn('chronicle_id', $chronicles);
            $parts[] = DB::table('chronicle_entry_entities')->select('entity_id')->whereIn('entry_id', $entries);
            $primary = $this->primaryRelationships($chronicles);
            $parts[] = DB::table('relationships')->select('source_entity_id')->whereIn('relationship_id', $primary);
            $parts[] = DB::table('relationships')->select('target_entity_id')->whereIn('relationship_id', $primary);
        }

        if ($parts === []) {
            return null;
        }

        $set = array_shift($parts);
        foreach ($parts as $part) {
            $set->union($part);
        }

        return $set;
    }

    /** @param list<string> $ids validated uuids, so the array literal is safe */
    private function anyOf(QueryBuilder $query, string $column, array $ids): QueryBuilder
    {
        return $query->whereRaw("{$column} = any(?::uuid[])", ['{'.implode(',', $ids).'}']);
    }

    private function chronicleSet(ExportScope $scope): ?QueryBuilder
    {
        if ($scope->chronicleSlugs() === []) {
            return null;
        }

        return DB::table('chronicles')->select('chronicle_id')->whereIn('slug', $scope->chronicleSlugs());
    }

    private function primaryRelationships(QueryBuilder $chronicles): QueryBuilder
    {
        return DB::table('chronicle_entries')->select('primary_relationship_id')
            ->whereIn('chronicle_id', $chronicles)
            ->whereNotNull('primary_relationship_id');
    }

    private function entities(): QueryBuilder
    {
        return DB::table('entities')->select('entity_id');
    }
}
