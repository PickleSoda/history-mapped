<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Enums\TagSource;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
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
        // Nested selects are built from RecordType::nestedKeys() plus explicit extras (the FK, geojson).
        $nested = RecordType::Entities->nestedKeys();

        return Entity::query()
            ->select(self::COLUMNS)
            ->with([
                'aliases' => fn (Relation $q) => $q->select(['entity_id', ...$nested['aliases']]),
                'entityTags' => fn (Relation $q) => $q
                    ->select(['entity_id', 'tag', 'source']) // `slug` is stored in column `tag`
                    ->whereIn('source', TagSource::exported()),
                'temporalRanges' => fn (Relation $q) => $q->select(['entity_id', ...$nested['temporal_ranges']]),
                'locations' => fn (Relation $q) => $q
                    ->select(['entity_id', ...array_diff($nested['locations'], ['geom', 'territory_geom'])])
                    ->selectRaw('ST_AsGeoJSON(geom, 7) as geom_geojson')
                    ->selectRaw('ST_AsGeoJSON(territory_geom, 7) as territory_geom_geojson'),
            ]);
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof Entity);
        $e = $model;
        // Enum and text columns are emitted from the raw DB value, so an unknown value is exported
        // as-is and reported by the validator instead of aborting the export.
        $r = fn (string $col) => JsonLine::raw($e, $col);

        return [
            'id' => $r('entity_id'),
            'name' => $r('name'),
            'entity_type' => $r('entity_type'),
            'wikidata_id' => $r('wikidata_id'),
            'summary' => $r('summary'),
            'significance' => $r('significance'),
            'impact_score' => $r('impact_score'),
            'display_priority' => $r('display_priority'),
            'icon_class' => $r('icon_class'),
            'confidence' => $r('confidence'),
            'verification_status' => $r('verification_status'),
            'date_method' => $r('date_method'),
            'date_confidence' => $r('date_confidence'),
            'duration_type' => $r('duration_type'),
            'location_method' => $r('location_method'),
            'location_confidence' => $r('location_confidence'),
            'primary_geo_ref_id' => $r('primary_geo_ref_id'),
            'attributes' => $profile->filterAttributes(JsonLine::jsonbObject($e, 'attributes') ?? (object) []),
            'source_citations' => JsonLine::jsonbObject($e, 'source_citations'),
            'aliases' => $this->aliases($e),
            'tags' => TagList::build($e->entityTags),
            'temporal_ranges' => $this->temporalRanges($e),
            'locations' => $this->locations($e),
        ];
    }

    /** @return list<array<string, mixed>> */
    private function aliases(Entity $e): array
    {
        $items = $e->aliases->map(fn (EntityAlias $a) => [
            'name' => JsonLine::raw($a, 'name'),
            'language' => JsonLine::raw($a, 'language'),
            'source' => JsonLine::raw($a, 'source'),
            'is_primary' => (bool) JsonLine::raw($a, 'is_primary'),
        ])->all();

        return JsonLine::sortList($items, fn (array $a) => [! $a['is_primary'], $a['name'], $a['language'] === null, $a['language'] ?? '']);
    }

    /** @return list<array<string, mixed>> */
    private function temporalRanges(Entity $e): array
    {
        $items = $e->temporalRanges->map(fn (EntityTemporalRange $t) => [
            'range_type' => JsonLine::raw($t, 'range_type'),
            'start_year' => JsonLine::raw($t, 'start_year'),
            'end_year' => JsonLine::raw($t, 'end_year'),
            'start_date' => JsonLine::raw($t, 'start_date'),
            'end_date' => JsonLine::raw($t, 'end_date'),
            'duration_type' => JsonLine::raw($t, 'duration_type'),
            'date_method' => JsonLine::raw($t, 'date_method'),
            'date_confidence' => JsonLine::raw($t, 'date_confidence'),
            'is_primary' => (bool) JsonLine::raw($t, 'is_primary'),
            'notes' => JsonLine::raw($t, 'notes'),
        ])->all();

        // Null years sort lowest.
        return JsonLine::sortList($items, fn (array $t) => [! $t['is_primary'], $t['range_type'], $t['start_year'] ?? PHP_INT_MIN, $t['end_year'] ?? PHP_INT_MIN]);
    }

    /** @return list<array<string, mixed>> */
    private function locations(Entity $e): array
    {
        $items = $e->locations->map(fn (EntityLocation $l) => [
            'location_name' => JsonLine::raw($l, 'location_name'),
            'location_method' => JsonLine::raw($l, 'location_method'),
            'location_confidence' => JsonLine::raw($l, 'location_confidence'),
            'is_primary' => (bool) JsonLine::raw($l, 'is_primary'),
            'notes' => JsonLine::raw($l, 'notes'),
            'geom' => $l->geom, // GeoJson cast reads the pre-selected geom_geojson
            'territory_geom' => $l->territory_geom,
        ])->all();

        // Null names sort as ''.
        return JsonLine::sortList($items, fn (array $l) => [! $l['is_primary'], $l['location_name'] ?? '']);
    }
}
