<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\EntityTimelineEntryResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class EntityTimelineController extends Controller
{
    /**
     * GET /api/v1/entities/{entity}/timeline
     */
    public function index(string $entity): AnonymousResourceCollection
    {
        $entityModel = Entity::where('entity_id', $entity)->firstOrFail();

        $entries = $entityModel->timelineEntries()
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->orderBy('created_at')
            ->get();

        return EntityTimelineEntryResource::collection($entries);
    }
}
