<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Chronicle;
use App\Models\MapStory;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Pagination\AbstractPaginator;

/** @mixin Chronicle */
class ChronicleResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'chronicle_id' => $this->chronicle_id,
            'title' => $this->title,
            'slug' => $this->slug,
            'description' => $this->description,
            'source_type' => $this->source_type?->value,
            'source_reference' => $this->source_reference,
            'status' => $this->status?->value,
            'start_year' => $this->start_year,
            'end_year' => $this->end_year,
            'impact_score' => $this->impact_score,
            'approximate_location' => $this->approximate_location,
            'metadata' => $this->metadata,
            // The chronicle's map layer (a map story attached to it), or null.
            'map_story' => $this->mapStory(),
            'entry_count' => $this->whenCounted('entries'),
            // Tag slugs (with ancestors); names/facets come from GET /tags.
            'tags' => $this->whenLoaded('tags', fn () => $this->tags->pluck('slug')->values()->all()),
            'entries' => $this->when(
                $this->relationLoaded('entries'),
                fn () => ChronicleEntryResource::collection($this->entries),
            ),
            'created_at' => $this->created_at,
            'updated_at' => $this->updated_at,
        ];
    }

    /**
     * Preload the map layers of a page of chronicles in one query.
     *
     * @param  mixed  $resource
     */
    public static function collection($resource): AnonymousResourceCollection
    {
        $chronicles = $resource instanceof AbstractPaginator ? $resource->getCollection() : collect($resource);
        $ids = $chronicles->map(fn (mixed $c) => $c instanceof Chronicle ? $c->chronicle_id : null)->filter()->values()->all();
        $stories = $ids === [] ? collect() : MapStory::query()
            ->whereIn('chronicle_id', $ids)
            ->orderBy('slug')
            ->get(MapStory::SUMMARY_COLUMNS)
            ->groupBy('chronicle_id');
        foreach ($chronicles as $chronicle) {
            if ($chronicle instanceof Chronicle) {
                $chronicle->setRelation('mapStory', $stories->get($chronicle->chronicle_id)?->first());
            }
        }

        return parent::collection($resource);
    }

    /** @return array{id: string, slug: string, kind: string, title: string, year: int|null, step_count: int}|null */
    private function mapStory(): ?array
    {
        $story = $this->resource->relationLoaded('mapStory')
            ? $this->resource->getRelation('mapStory')
            : MapStory::query()->where('chronicle_id', $this->chronicle_id)->orderBy('slug')->first(MapStory::SUMMARY_COLUMNS);

        return $story instanceof MapStory ? MapStoryResource::summary($story) : null;
    }
}
