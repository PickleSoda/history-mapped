<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Tag;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A tag as GET /tags lists it (and a curated collection embeds it). Load the
 * usage counts first: `withCount(['chronicles', 'entities'])`.
 *
 * @mixin Tag
 */
class TagResource extends JsonResource
{
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
