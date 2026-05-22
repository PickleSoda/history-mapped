<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\EntityTimelineEntrySummaryResource;
use App\Http\Api\V1\Resources\EntityTimelineEntryResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\Resources\Json\JsonResource;
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
            ->select([
                'timeline_entry_id',
                'entity_id',
                'entry_kind',
                'start_year',
                'end_year',
                'title',
                'description',
                'location_entity_id',
                'source_table',
                'source_id',
                'relationship_type',
                'related_entity_id',
                'related_entity_name',
                'derived_at',
                'created_at',
                'updated_at',
            ])
            ->selectRaw('geom IS NOT NULL as has_geom')
            ->selectRaw('territory_geom IS NOT NULL as has_territory_geom')
            ->selectRaw("CASE WHEN geom IS NOT NULL AND ST_GeometryType(geom) = 'ST_Point' THEN ST_AsGeoJSON(geom)::jsonb ELSE NULL END as geom_geojson")
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->orderBy('created_at')
            ->get();

        return EntityTimelineEntrySummaryResource::collection($entries);
    }

    /**
     * GET /api/v1/entities/{entity}/timeline/{timelineEntry}
     */
    public function show(string $entity, string $timelineEntry): JsonResource
    {
        $entityModel = Entity::where('entity_id', $entity)->firstOrFail();

        $entry = $entityModel->timelineEntries()
            ->where('timeline_entry_id', $timelineEntry)
            ->firstOrFail();

        return new EntityTimelineEntryResource($entry);
    }
}
