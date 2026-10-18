<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Enums\TagSource;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTag;
use App\Models\EntityTemporalRange;
use App\Support\ContentBundle\JsonLine;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\Relation;

/**
 * Entity -> bundle line. Selects explicit columns (never the ~12 KB `embedding`) and eager-loads
 * every nested list, so exporting N entities costs a constant number of queries.
 */
final class EntitySerializer implements RecordSerializer
{
    private const COLUMNS = [
        'entity_id', 'name', 'entity_type', 'wikidata_id', 'summary', 'significance', 'impact_score',
        'display_priority', 'icon_class', 'confidence', 'verification_status', 'date_method',
        'date_confidence', 'duration_type', 'location_method', 'location_confidence',
        'primary_geo_ref_id', 'attributes', 'source_citations',
    ];

    public function type(): RecordType
    {
        return RecordType::Entities;
    }

    public function query(): Builder
    {
        return Entity::query()
            ->select(self::COLUMNS)
            ->with([
                'aliases' => fn (Relation $q) => $q->select(['entity_id', ...RecordType::Entities->nestedKeys()['aliases']]),
                'entityTags' => fn (Relation $q) => $q
                    ->select(['entity_id', 'tag', 'source'])
                    ->whereIn('source', [TagSource::Manual->value, TagSource::Curated->value]),
                'temporalRanges' => fn (Relation $q) => $q->select(['entity_id', ...RecordType::Entities->nestedKeys()['temporal_ranges']]),
                'locations' => fn (Relation $q) => $q
                    ->select(['entity_id', 'location_name', 'location_method', 'location_confidence', 'is_primary', 'notes'])
                    ->selectRaw('ST_AsGeoJSON(geom, 7) as geom_geojson')
                    ->selectRaw('ST_AsGeoJSON(territory_geom, 7) as territory_geom_geojson'),
            ]);
    }

    public function serialize(Model $model, Profile $profile): array
    {
        /** @var Entity $e */
        $e = $model;

        $attributes = $e->attributes ?? [];
        if ($profile === Profile::Public) {
            $attributes = array_filter($attributes, fn ($key) => ! str_starts_with((string) $key, '_'), ARRAY_FILTER_USE_KEY);
        }

        return [
            'id' => $e->entity_id,
            'name' => $e->name,
            'entity_type' => $e->entity_type?->value,
            'wikidata_id' => $e->wikidata_id,
            'summary' => $e->summary,
            'significance' => $e->significance,
            'impact_score' => $e->impact_score,
            'display_priority' => $e->display_priority,
            'icon_class' => $e->icon_class?->value,
            'confidence' => $e->confidence?->value,
            'verification_status' => $e->verification_status?->value,
            'date_method' => $e->date_method?->value,
            'date_confidence' => $e->date_confidence?->value,
            'duration_type' => $e->duration_type?->value,
            'location_method' => $e->location_method?->value,
            'location_confidence' => $e->location_confidence?->value,
            'primary_geo_ref_id' => $e->primary_geo_ref_id,
            'attributes' => JsonLine::object($attributes),
            'source_citations' => JsonLine::object($e->source_citations),
            'aliases' => $this->aliases($e),
            'tags' => $this->tags($e),
            'temporal_ranges' => $this->temporalRanges($e),
            'locations' => $this->locations($e),
        ];
    }

    /** @return list<array<string, mixed>> */
    private function aliases(Entity $e): array
    {
        return $e->aliases
            ->map(fn (EntityAlias $a) => [
                'name' => $a->name,
                'language' => $a->language,
                'source' => $a->source,
                'is_primary' => (bool) $a->is_primary,
            ])
            ->sort(fn (array $a, array $b) => [! $a['is_primary'], $a['name'], $a['language'] === null, $a['language']]
                <=> [! $b['is_primary'], $b['name'], $b['language'] === null, $b['language']])
            ->values()
            ->all();
    }

    /** @return list<array{slug: string, source: string}> */
    private function tags(Entity $e): array
    {
        return $e->entityTags
            ->map(fn (EntityTag $t) => ['slug' => $t->tag, 'source' => $t->source])
            ->sortBy('slug', SORT_STRING)
            ->values()
            ->all();
    }

    /** @return list<array<string, mixed>> */
    private function temporalRanges(Entity $e): array
    {
        return $e->temporalRanges
            ->map(fn (EntityTemporalRange $r) => [
                'range_type' => $r->range_type,
                'start_year' => $r->start_year,
                'end_year' => $r->end_year,
                'start_date' => $r->start_date,
                'end_date' => $r->end_date,
                'duration_type' => $r->duration_type?->value,
                'date_method' => $r->date_method?->value,
                'date_confidence' => $r->date_confidence?->value,
                'is_primary' => (bool) $r->is_primary,
                'notes' => $r->notes,
            ])
            ->sort(fn (array $a, array $b) => [! $a['is_primary'], $a['range_type'], $a['start_year'] ?? PHP_INT_MIN, $a['end_year'] ?? PHP_INT_MIN]
                <=> [! $b['is_primary'], $b['range_type'], $b['start_year'] ?? PHP_INT_MIN, $b['end_year'] ?? PHP_INT_MIN])
            ->values()
            ->all();
    }

    /** @return list<array<string, mixed>> */
    private function locations(Entity $e): array
    {
        return $e->locations
            ->map(fn (EntityLocation $l) => [
                'location_name' => $l->location_name,
                'location_method' => $l->location_method?->value,
                'location_confidence' => $l->location_confidence?->value,
                'is_primary' => (bool) $l->is_primary,
                'notes' => $l->notes,
                'geom' => $l->geom,
                'territory_geom' => $l->territory_geom,
            ])
            ->sort(fn (array $a, array $b) => [! $a['is_primary'], $a['location_name'] ?? '']
                <=> [! $b['is_primary'], $b['location_name'] ?? ''])
            ->values()
            ->all();
    }
}
