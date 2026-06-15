<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\EntityTimelineEntryResource;
use App\Http\Api\V1\Resources\EntityTimelineEntrySummaryResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\EntityTimelineEntry;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

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

        $this->decorateWithOhmRef($entries, $entity);

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

        $this->decorateWithOhmRef(collect([$entry]), $entity);

        return new EntityTimelineEntryResource($entry);
    }

    /**
     * Stamp each timeline entry with the entity's active OHM geo-ref (one query
     * per request — the ref is a property of the entity, identical across all
     * its entries). Under the borders-from-OHM policy (D19) the history panel
     * uses this to highlight the OHM basemap feature instead of a stored polygon.
     *
     * @param  Collection<int, EntityTimelineEntry>  $entries
     */
    private function decorateWithOhmRef(Collection $entries, string $entityId): void
    {
        $ref = DB::table('entity_geo_refs')
            ->where('entity_id', $entityId)
            ->where('provider', 'ohm')
            ->where('is_active', true)
            ->orderByRaw("(match_role = 'primary') DESC")
            ->orderByDesc('updated_at')
            ->first(['external_id', 'external_type']);

        $externalId = $ref->external_id ?? null;
        $externalType = $ref->external_type ?? null;

        foreach ($entries as $entry) {
            $entry->setAttribute('ohm_external_id', $externalId);
            $entry->setAttribute('ohm_external_type', $externalType);
        }
    }
}
