<?php

declare(strict_types=1);

namespace App\Actions\Collection;

use App\Http\Api\V1\Resources\ChronicleResource;
use App\Http\Api\V1\Resources\EntitySummaryResource;
use App\Http\Api\V1\Resources\MapStorySummaryResource;
use App\Http\Api\V1\Resources\TagResource;
use App\Models\Chronicle;
use App\Models\Collection;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\Tag;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Resolve curated collections' items when they are served, one query per
 * kind however many items or collections there are:
 *  - entity: by Wikidata id (`entities.wikidata_id`; the most prominent
 *    entity should two share one) or by uuid, as EntitySummaryResource;
 *  - chronicle: by slug, as ChronicleResource without entries;
 *  - story: by slug, as MapStorySummaryResource;
 *  - tag: by slug, as the GET /tags row (TagResource).
 * A ref that resolves to nothing is dropped (and logged when a collection
 * is shown), never an error.
 */
class ResolveCollectionItemsAction
{
    /**
     * One collection's items in order, each as `{kind, note, <kind>: payload}`.
     *
     * @return list<array<string, mixed>>
     */
    public function __invoke(Collection $collection): array
    {
        $resolved = $this->lookup(self::refsByKind([$collection]), full: true);

        $out = [];
        foreach ($collection->items ?? [] as $item) {
            $kind = is_array($item) ? ($item['kind'] ?? null) : null;
            $ref = is_array($item) ? ($item['ref'] ?? null) : null;
            $payload = is_string($kind) && is_string($ref) ? ($resolved[$kind][self::key($kind, $ref)] ?? null) : null;
            if ($payload === null) {
                Log::warning('Collection item does not resolve; dropped', ['collection' => $collection->slug, 'kind' => $kind, 'ref' => $ref]);

                continue;
            }
            $out[] = ['kind' => $kind, 'note' => $item['note'] ?? null, $kind => $payload];
        }

        return $out;
    }

    /**
     * How many of each collection's items resolve, keyed by collection id:
     * one existence query per kind for all of them.
     *
     * @param  iterable<Collection>  $collections
     * @return array<string, array{item_count: int, items_by_kind: array<string, int>}>
     */
    public function counts(iterable $collections): array
    {
        $collections = collect($collections);
        $found = $this->lookup(self::refsByKind($collections), full: false);

        return $collections->mapWithKeys(fn (Collection $c) => [$c->collection_id => self::tally(
            array_values(array_filter(
                $c->items ?? [],
                fn (mixed $item) => is_array($item) && is_string($item['kind'] ?? null) && is_string($item['ref'] ?? null)
                    && isset($found[$item['kind']][self::key($item['kind'], $item['ref'])]),
            )),
        )])->all();
    }

    /**
     * Each collection's cover entity as EntitySummaryResource (or null), keyed
     * by collection id, in one query.
     *
     * @param  iterable<Collection>  $collections
     * @return array<string, array<string, mixed>|null>
     */
    public function covers(iterable $collections): array
    {
        $collections = collect($collections);
        $ids = $collections->pluck('cover_entity_id')->filter()->unique()->values()->all();
        $entities = $ids === [] ? collect() : Entity::query()->withGeoJson()->whereIn('entities.entity_id', $ids)->get()->keyBy('entity_id');

        return $collections->mapWithKeys(fn (Collection $c) => [$c->collection_id => $entities->has((string) $c->cover_entity_id)
            ? (new EntitySummaryResource($entities->get($c->cover_entity_id)))->resolve()
            : null,
        ])->all();
    }

    /**
     * Count items (resolved, or with a kind) by kind.
     *
     * @param  list<array<string, mixed>>  $items
     * @return array{item_count: int, items_by_kind: array<string, int>}
     */
    public static function tally(array $items): array
    {
        $byKind = array_fill_keys(Collection::KINDS, 0);
        foreach ($items as $item) {
            if (isset($byKind[$item['kind'] ?? ''])) {
                $byKind[$item['kind']]++;
            }
        }

        return ['item_count' => array_sum($byKind), 'items_by_kind' => $byKind];
    }

    /**
     * The well-formed refs of every kind across the collections (a malformed
     * one could not match and would only break the query).
     *
     * @param  iterable<Collection>  $collections
     * @return array<string, list<string>>
     */
    private static function refsByKind(iterable $collections): array
    {
        $refs = array_fill_keys(Collection::KINDS, []);
        foreach ($collections as $collection) {
            foreach ($collection->items ?? [] as $item) {
                $kind = is_array($item) ? ($item['kind'] ?? null) : null;
                $ref = is_array($item) ? ($item['ref'] ?? null) : null;
                if (! is_string($kind) || ! isset($refs[$kind]) || ! is_string($ref)) {
                    continue;
                }
                $wellFormed = $kind === 'entity' ? Collection::isEntityRef($ref) : preg_match(Collection::REF_PATTERN, $ref) === 1;
                if ($wellFormed) {
                    $refs[$kind][] = self::key($kind, $ref);
                }
            }
        }

        return array_map(fn (array $list) => array_values(array_unique($list)), $refs);
    }

    /** Entity uuids match in any case; everything else as written. */
    private static function key(string $kind, string $ref): string
    {
        return $kind === 'entity' && Str::isUuid($ref) ? Str::lower($ref) : $ref;
    }

    /**
     * Resolve refs, one query per kind: `$full` gives each found ref its
     * payload, otherwise just `true`.
     *
     * @param  array<string, list<string>>  $refs
     * @return array<string, array<string, mixed>>
     */
    private function lookup(array $refs, bool $full): array
    {
        return [
            'entity' => $this->entities($refs['entity'], $full),
            'chronicle' => $this->chronicles($refs['chronicle'], $full),
            'story' => $this->stories($refs['story'], $full),
            'tag' => $this->tags($refs['tag'], $full),
        ];
    }

    /**
     * @param  list<string>  $refs  Wikidata ids and uuids
     * @return array<string, mixed>
     */
    private function entities(array $refs, bool $full): array
    {
        if ($refs === []) {
            return [];
        }
        $qids = array_values(array_filter($refs, fn (string $r) => ! Str::isUuid($r)));
        $uuids = array_values(array_filter($refs, fn (string $r) => Str::isUuid($r)));

        $query = $full ? Entity::query()->withGeoJson() : Entity::query()->select(['entities.entity_id', 'entities.wikidata_id']);
        $entities = $query
            ->where(fn (Builder $q) => $q->whereIn('entities.wikidata_id', $qids)->orWhereIn('entities.entity_id', $uuids))
            ->orderByRaw('entities.impact_score DESC NULLS LAST')
            ->get();

        $out = [];
        foreach ($entities as $entity) {
            $payload = $full ? (new EntitySummaryResource($entity))->resolve() : true;
            if (is_string($entity->wikidata_id) && in_array($entity->wikidata_id, $qids, true)) {
                $out[$entity->wikidata_id] ??= $payload;
            }
            $out[$entity->entity_id] ??= $payload;
        }

        return $out;
    }

    /**
     * @param  list<string>  $slugs
     * @return array<string, mixed>
     */
    private function chronicles(array $slugs, bool $full): array
    {
        if ($slugs === []) {
            return [];
        }
        if (! $full) {
            return Chronicle::query()->whereIn('slug', $slugs)->pluck('slug')->flip()->map(fn () => true)->all();
        }

        $chronicles = Chronicle::query()->whereIn('slug', $slugs)->withCount('entries')->with('tags')->get();

        return collect(ChronicleResource::collection($chronicles)->resolve())->keyBy('slug')->all();
    }

    /**
     * @param  list<string>  $slugs
     * @return array<string, mixed>
     */
    private function stories(array $slugs, bool $full): array
    {
        if ($slugs === []) {
            return [];
        }
        if (! $full) {
            return MapStory::query()->whereIn('slug', $slugs)->pluck('slug')->flip()->map(fn () => true)->all();
        }

        return MapStory::query()
            ->select(MapStory::SUMMARY_COLUMNS)
            ->with(MapStorySummaryResource::RELATIONS)
            ->whereIn('slug', $slugs)
            ->get()
            ->mapWithKeys(fn (MapStory $s) => [$s->slug => MapStorySummaryResource::row($s)])
            ->all();
    }

    /**
     * @param  list<string>  $slugs
     * @return array<string, mixed>
     */
    private function tags(array $slugs, bool $full): array
    {
        if ($slugs === []) {
            return [];
        }
        if (! $full) {
            return Tag::query()->whereIn('slug', $slugs)->pluck('slug')->flip()->map(fn () => true)->all();
        }

        return Tag::query()
            ->whereIn('slug', $slugs)
            ->withCount(['chronicles', 'entities'])
            ->get()
            ->mapWithKeys(fn (Tag $t) => [$t->slug => TagResource::row($t)])
            ->all();
    }
}
