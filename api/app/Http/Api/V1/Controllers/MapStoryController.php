<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\MapStoryResource;
use App\Http\Controllers\Controller;
use App\Models\MapStory;

class MapStoryController extends Controller
{
    /**
     * GET /api/v1/map-stories/{slug}
     *
     * A battle map with its whole document (sides, units, terrain, steps); an
     * entity's detail lists its stories without documents.
     */
    public function show(string $slug): MapStoryResource
    {
        return new MapStoryResource(MapStory::query()->where('slug', $slug)->firstOrFail());
    }
}
