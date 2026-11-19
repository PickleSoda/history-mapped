<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Tag;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A tag as GET /tags lists it (and a curated collection embeds it). Load the
 * usage counts first: `TagResource::withCounts(Tag::query())`.
 *
 * @mixin Tag
 */
class TagResource extends JsonResource
{
    /**
     * Add the usage counts row() reads. Archived chronicles are hidden from the
     * public site, so they don't count. Entity counts come from the cached
     * Tag::entityCounts(), set on each tag once the query has run: counting
     * 2.4M entity_tags rows per request took about 1 s on the droplet.
     *
     * @template TModel of Tag
     *
     * @param  Builder<TModel>  $query
     * @return Builder<TModel>
     */
    public static function withCounts(Builder $query): Builder
    {
        return $query
            ->withCount(['chronicles' => fn (Builder $q) => $q->notArchived()])
            ->afterQuery(function (Collection $tags): void {
                $counts = Tag::entityCounts();
                foreach ($tags as $tag) {
                    $tag->setAttribute('entities_count', $counts[$tag->slug] ?? 0);
                }
            });
    }

    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return self::row($this->resource);
    }

    /**
     * @return array{slug: string, name: string, facet: string, parent: string|null, description: string|null, start_year: int|null, end_year: int|null, chronicle_count: int, entity_count: int}
     */
    public static function row(Tag $tag): array
    {
        return [
            'slug' => $tag->slug,
            'name' => $tag->name,
            'facet' => $tag->facet->value,
            'parent' => $tag->parent_slug,
            'description' => $tag->description,
            'start_year' => $tag->start_year,
            'end_year' => $tag->end_year,
            'chronicle_count' => (int) $tag->chronicles_count,
            'entity_count' => (int) $tag->entities_count,
        ];
    }
}
