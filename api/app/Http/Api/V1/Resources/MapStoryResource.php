<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\MapStory;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\Collection;

/**
 * A map story with its document (GET /map-stories/{slug}). `entity_id` or
 * `chronicle_id` may be null (a story belongs to at least one); `period` is
 * its [start, end] year span.
 *
 * @mixin MapStory
 */
class MapStoryResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            ...self::summary($this->resource),
            'entity_id' => $this->entity_id,
            'chronicle_id' => $this->chronicle_id,
            'period' => $this->period_start === null ? null : ['start' => $this->period_start, 'end' => $this->period_end ?? $this->period_start],
            'ambient' => (bool) $this->ambient,
            'document' => $this->document,
        ];
    }

    /**
     * The list-view shape embedded in an entity's and a chronicle's detail.
     *
     * @return array{id: string, slug: string, kind: string, title: string, year: int|null, step_count: int}
     */
    public static function summary(MapStory $story): array
    {
        return [
            'id' => $story->story_id,
            'slug' => $story->slug,
            'kind' => $story->kind,
            'title' => $story->title,
            'year' => $story->year,
            'step_count' => $story->step_count,
        ];
    }

    /**
     * @param  Collection<int, MapStory>  $stories
     * @return list<array{id: string, slug: string, kind: string, title: string, year: int|null, step_count: int}>
     */
    public static function summaries(Collection $stories): array
    {
        return $stories->map(fn (MapStory $story) => self::summary($story))->values()->all();
    }
}
