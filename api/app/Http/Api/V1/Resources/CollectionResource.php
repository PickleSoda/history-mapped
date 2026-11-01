<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Collection;

/**
 * A curated collection's card (GET /collections) and the head of its page
 * (GET /collections/{slug}). The cover and the counts come resolved
 * (ResolveCollectionItemsAction), so the counts only include items that
 * resolve.
 */
final class CollectionResource
{
    /**
     * @param  array<string, mixed>|null  $cover  EntitySummaryResource
     * @param  array{item_count: int, items_by_kind: array<string, int>}  $counts
     * @return array{slug: string, title: string, subtitle: string|null, description: string|null, cover: array<string, mixed>|null, item_count: int, items_by_kind: array<string, int>}
     */
    public static function summary(Collection $collection, ?array $cover, array $counts): array
    {
        return [
            'slug' => $collection->slug,
            'title' => $collection->title,
            'subtitle' => $collection->subtitle,
            'description' => $collection->description,
            'cover' => $cover,
            'item_count' => $counts['item_count'],
            'items_by_kind' => $counts['items_by_kind'],
        ];
    }
}
