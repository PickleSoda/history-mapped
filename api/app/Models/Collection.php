<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\CollectionStatus;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

/**
 * A curated collection: an editorial, ordered set of entities, chronicles,
 * map stories and tags for the public site's browse pages. Authored as
 * resources/collections/<slug>.json and loaded by `collections:sync`
 * (SyncCollectionFileAction); there is no admin editing.
 *
 * `items` is a list of `{kind, ref, note?}`. An entity's `ref` is its
 * Wikidata id (`Q…`, or its uuid as a fallback); a chronicle's, story's or
 * tag's is its slug. Items are resolved when served
 * (ResolveCollectionItemsAction), not when synced. The format and the API
 * are documented in docs/schemas/collections.md.
 *
 * @property list<array{kind: string, ref: string, note?: string}> $items
 */
#[Fillable(['slug', 'title', 'subtitle', 'description', 'cover_entity_id', 'items', 'status', 'sort_order'])]
class Collection extends Model
{
    use HasUuids;

    protected $table = 'collections';

    protected $primaryKey = 'collection_id';

    /** Item kinds, in the order `items_by_kind` lists them. */
    public const KINDS = ['entity', 'chronicle', 'story', 'tag'];

    /** A Wikidata item id. */
    public const QID_PATTERN = '/^Q[1-9][0-9]*$/';

    /** A collection's own slug (and file name). */
    public const SLUG_PATTERN = '/^[a-z0-9]+(?:-[a-z0-9]+)*$/';

    /** A chronicle, map-story or tag slug: these may carry accents or a trailing hyphen, so no spaces or slashes is all. */
    public const REF_PATTERN = '/^[^\s\/]+$/u';

    protected function casts(): array
    {
        return [
            'items' => 'array',
            'status' => CollectionStatus::class,
            'sort_order' => 'integer',
        ];
    }

    /** True for an entity ref that names a Wikidata id or an entity uuid. */
    public static function isEntityRef(string $ref): bool
    {
        return preg_match(self::QID_PATTERN, $ref) === 1 || Str::isUuid($ref);
    }

    /**
     * @param  Builder<Collection>  $query
     */
    public function scopePublished(Builder $query): void
    {
        $query->where('status', CollectionStatus::Published->value);
    }

    /**
     * Display order: `sort_order`, then title.
     *
     * @param  Builder<Collection>  $query
     */
    public function scopeOrdered(Builder $query): void
    {
        $query->orderBy('sort_order')->orderBy('title')->orderBy('slug');
    }

    /** @return BelongsTo<Entity, $this> */
    public function cover(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'cover_entity_id', 'entity_id');
    }
}
