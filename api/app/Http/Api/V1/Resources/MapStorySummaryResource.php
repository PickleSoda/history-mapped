<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\MapStory;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A map story in a list (GET /map-stories, a curated collection): the summary
 * an entity's and a chronicle's detail embed (MapStoryResource::summary())
 * plus what it is attached to. Load `entity:entity_id,name,entity_type` and
 * `chronicle:chronicle_id,slug,title` first (MapStorySummaryResource::RELATIONS).
 *
 * @mixin MapStory
 */
class MapStorySummaryResource extends JsonResource
{
    /** Eager loads for the attached entity and chronicle. */
    public const RELATIONS = ['entity:entity_id,name,entity_type', 'chronicle:chronicle_id,slug,title'];

    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return self::row($this->resource);
    }

    /**
     * @return array{id: string, slug: string, kind: string, title: string, year: int|null, step_count: int, entity: array{id: string, name: string, entity_type: string|null}|null, chronicle: array{slug: string, title: string}|null}
     */
    public static function row(MapStory $story): array
    {
        $entity = $story->entity;
        $chronicle = $story->chronicle;

        return [
            ...MapStoryResource::summary($story),
            'entity' => $entity === null ? null : [
                'id' => $entity->entity_id,
                'name' => $entity->name,
                'entity_type' => $entity->entity_type?->value,
            ],
            'chronicle' => $chronicle === null ? null : [
                'slug' => $chronicle->slug,
                'title' => $chronicle->title,
            ],
        ];
    }
}
