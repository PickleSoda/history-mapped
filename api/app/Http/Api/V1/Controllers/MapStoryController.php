<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\MapStory\ListMapStoriesAction;
use App\Http\Api\V1\Requests\ListMapStoriesRequest;
use App\Http\Api\V1\Resources\MapStoryResource;
use App\Http\Api\V1\Resources\MapStorySummaryResource;
use App\Http\Controllers\Controller;
use App\Models\MapStory;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class MapStoryController extends Controller
{
    /**
     * GET /api/v1/map-stories?kind=battle,siege&sort=year|title&per_page=20&page=1
     *
     * Every map story as a summary (no document) with the entity and the
     * chronicle it belongs to, paginated (`meta`, `links`).
     */
    public function index(ListMapStoriesRequest $request, ListMapStoriesAction $list): AnonymousResourceCollection
    {
        return MapStorySummaryResource::collection($list($request->validated()));
    }

    /**
     * GET /api/v1/map-stories/{slug}
     *
     * A map story with its whole document (sides, units, features, steps); an
     * entity's or chronicle's detail lists its stories without documents.
     */
    public function show(string $slug): MapStoryResource
    {
        return new MapStoryResource(MapStory::query()->where('slug', $slug)->firstOrFail(MapStory::DETAIL_COLUMNS));
    }
}
