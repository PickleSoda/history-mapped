<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\TagFacet;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

#[Fillable([
    'slug', 'name', 'facet', 'parent_slug', 'description', 'start_year', 'end_year', 'sort_order',
])]
class Tag extends Model
{
    protected $table = 'tags';

    protected $primaryKey = 'slug';

    public $incrementing = false;

    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'facet' => TagFacet::class,
            'start_year' => 'integer',
            'end_year' => 'integer',
            'sort_order' => 'integer',
        ];
    }

    /** @return BelongsTo<Tag, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(Tag::class, 'parent_slug', 'slug');
    }

    /** @return HasMany<Tag, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(Tag::class, 'parent_slug', 'slug');
    }

    /** @return BelongsToMany<Chronicle, $this> */
    public function chronicles(): BelongsToMany
    {
        return $this->belongsToMany(Chronicle::class, 'chronicle_tags', 'tag', 'chronicle_id', 'slug', 'chronicle_id');
    }

    /** @return BelongsToMany<Entity, $this> */
    public function entities(): BelongsToMany
    {
        return $this->belongsToMany(Entity::class, 'entity_tags', 'tag', 'entity_id', 'slug', 'entity_id');
    }

    /**
     * Group filter slugs by facet. A row matches when it has one tag from every
     * group: AND across facets, OR within one ("Medieval" + "Europe" + "Asia" =
     * medieval chronicles in Europe or Asia). Null when a slug is unknown, so
     * callers can return nothing rather than ignore the filter.
     *
     * @param  list<string>  $slugs
     * @return list<list<string>>|null
     */
    public static function filterGroups(array $slugs): ?array
    {
        $slugs = array_values(array_unique($slugs));
        if ($slugs === []) {
            return [];
        }

        $facets = self::query()->whereIn('slug', $slugs)->pluck('facet', 'slug');
        if ($facets->count() !== count($slugs)) {
            return null;
        }

        return $facets->keys()
            ->groupBy(fn (string $slug): string => $facets[$slug]->value)
            ->map(fn ($group): array => $group->values()->all())
            ->values()
            ->all();
    }

    /**
     * Drop tags implied by another tag in the set (keep "china", drop its
     * ancestors "east-asia" and "asia"), for compact display and editing.
     *
     * @param  iterable<Tag>  $tags
     * @return list<string>
     */
    public static function leafSlugs(iterable $tags): array
    {
        $tags = collect($tags);
        $parents = $tags->pluck('parent_slug')->filter()->flip();

        return $tags->reject(fn (Tag $t): bool => isset($parents[$t->slug]))
            ->pluck('slug')
            ->values()
            ->all();
    }

    /** Cache key of entityCounts(). */
    public const ENTITY_COUNTS_CACHE_KEY = 'tags:entity-counts';

    /** Seconds entityCounts() is kept; GET /tags is itself public for 300. */
    public const ENTITY_COUNTS_TTL = 600;

    /**
     * Entities per tag slug (tags with none are absent). Counting entity_tags
     * (2.4M rows at 641k entities) took about 1 s on the 1-vCPU droplet on
     * every GET /tags, so the counts are cached: `tags:sync` drops them, and
     * any other change (an admin edit, an import) shows within the TTL.
     *
     * @return array<string, int>
     */
    public static function entityCounts(): array
    {
        return Cache::remember(self::ENTITY_COUNTS_CACHE_KEY, self::ENTITY_COUNTS_TTL, fn (): array => DB::table('entity_tags')
            ->selectRaw('tag, count(*) AS n')
            ->groupBy('tag')
            ->pluck('n', 'tag')
            ->map(fn (mixed $n): int => (int) $n)
            ->all());
    }

    public static function forgetEntityCounts(): void
    {
        Cache::forget(self::ENTITY_COUNTS_CACHE_KEY);
    }

    /**
     * Facet display order, then the vocabulary's own order.
     *
     * @param  Builder<Tag>  $query
     */
    public function scopeOrdered(Builder $query): void
    {
        $query->orderByRaw("CASE facet WHEN 'era' THEN 0 WHEN 'region' THEN 1 WHEN 'theme' THEN 2 WHEN 'type' THEN 3 ELSE 4 END")
            ->orderBy('sort_order')
            ->orderBy('name');
    }
}
