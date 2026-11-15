<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Tag;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\Facades\DB;

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
     * public site, so they don't count. Entities are counted straight from
     * entity_tags: its foreign key cascades, so every row has its entity, and
     * a join to entities made the count take seconds once tags reached
     * millions of rows.
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
            ->addSelect(['entities_count' => DB::table('entity_tags')
                ->selectRaw('count(*)')
                ->whereColumn('entity_tags.tag', 'tags.slug')]);
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
