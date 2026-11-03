<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Collection\ResolveCollectionItemsAction;
use App\Http\Api\V1\Resources\CollectionResource;
use App\Http\Controllers\Controller;
use App\Models\Collection;
use Illuminate\Http\JsonResponse;

class CollectionController extends Controller
{
    /**
     * GET /api/v1/collections
     *
     * The published curated collections, by sort order then title, each with
     * its cover entity and how many items of each kind it holds.
     */
    public function index(ResolveCollectionItemsAction $resolve): JsonResponse
    {
        $collections = Collection::query()->published()->ordered()->get();
        $covers = $resolve->covers($collections);
        $counts = $resolve->counts($collections);

        return response()->json([
            'data' => $collections->map(fn (Collection $c): array => CollectionResource::summary(
                $c,
                $covers[$c->collection_id] ?? null,
                $counts[$c->collection_id],
            ))->values()->all(),
        ])->header('Cache-Control', 'public, max-age=300');
    }

    /**
     * GET /api/v1/collections/{slug}
     *
     * A published collection with its items resolved in order; refs that no
     * longer resolve are left out. 404 for an unknown or draft collection.
     */
    public function show(string $slug, ResolveCollectionItemsAction $resolve): JsonResponse
    {
        $collection = Collection::query()->published()->where('slug', $slug)->firstOrFail();
        $items = $resolve($collection);

        return response()->json([
            'data' => [
                ...CollectionResource::summary(
                    $collection,
                    $resolve->covers([$collection])[$collection->collection_id] ?? null,
                    ResolveCollectionItemsAction::tally($items),
                ),
                'items' => $items,
            ],
        ])->header('Cache-Control', 'public, max-age=300');
    }
}
