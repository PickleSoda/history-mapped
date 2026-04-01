<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\EntityGeoRef\CreateEntityGeoRefAction;
use App\Actions\EntityGeoRef\PrepareGeoRefAttachmentAction;
use App\Actions\EntityGeoRef\PruneOrphanSnapshotGeoRefAction;
use App\Actions\GeometrySnapshot\CreateSnapshotAction;
use App\Actions\GeometrySnapshot\DeleteSnapshotAction;
use App\Actions\GeometrySnapshot\ListSnapshotsAction;
use App\Actions\GeometrySnapshot\UpdateSnapshotAction;
use App\DTOs\GeometrySnapshotData;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreGeometrySnapshotRequest;
use App\Http\Requests\Admin\UpdateGeometrySnapshotRequest;
use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Http\JsonResponse;
use Illuminate\Validation\ValidationException;

/**
 * JSON controller for geometry snapshot CRUD.
 *
 * The snapshot builder UI is embedded in the entity edit Inertia page;
 * it communicates with these endpoints via fetch/router calls rather than
 * full Inertia page navigations.
 */
class GeometrySnapshotController extends Controller
{
    /**
     * List all snapshots for an entity.
     */
    public function index(Entity $entity, ListSnapshotsAction $listSnapshots): JsonResponse
    {
        $snapshots = $listSnapshots($entity);

        return response()->json([
            'snapshots' => $snapshots->map(fn (GeometrySnapshot $s) => self::buildSnapshotData($s)),
        ]);
    }

    /**
     * Create a new snapshot for an entity.
     */
    public function store(
        StoreGeometrySnapshotRequest $request,
        Entity $entity,
        CreateSnapshotAction $createSnapshot,
        PrepareGeoRefAttachmentAction $prepareGeoRefAttachment,
        CreateEntityGeoRefAction $createEntityGeoRef,
    ): JsonResponse {
        $validated = $this->prepareSnapshotPayload(
            $request->validated(),
            $entity,
            $prepareGeoRefAttachment,
            $createEntityGeoRef,
        );
        $validated['entity_id'] = $entity->entity_id;

        $data = GeometrySnapshotData::fromArray($validated);
        $snapshot = $createSnapshot($data, (string) $request->user()->id);

        return response()->json([
            'snapshot' => self::buildSnapshotData($snapshot),
        ], 201);
    }

    /**
     * Update an existing snapshot.
     */
    public function update(
        UpdateGeometrySnapshotRequest $request,
        Entity $entity,
        GeometrySnapshot $snapshot,
        UpdateSnapshotAction $updateSnapshot,
        PrepareGeoRefAttachmentAction $prepareGeoRefAttachment,
        CreateEntityGeoRefAction $createEntityGeoRef,
        PruneOrphanSnapshotGeoRefAction $pruneOrphanSnapshotGeoRef,
    ): JsonResponse {
        $this->authorizeSnapshotBelongsToEntity($snapshot, $entity);

        $previousGeoRefId = $snapshot->geo_ref_id;
        $validated = $this->prepareSnapshotPayload(
            $request->validated(),
            $entity,
            $prepareGeoRefAttachment,
            $createEntityGeoRef,
        );
        // Merge current values for required DTO fields not in the update payload
        $merged = array_merge([
            'entity_id' => $snapshot->entity_id,
            'year_start' => $snapshot->year_start,
            'year_end' => $snapshot->year_end,
            'display_priority' => $snapshot->display_priority,
            'geo_ref_id' => $snapshot->geo_ref_id,
        ], $validated);

        $data = GeometrySnapshotData::fromArray($merged);
        $snapshot = $updateSnapshot($snapshot, $data);

        if ($previousGeoRefId !== $snapshot->geo_ref_id) {
            $pruneOrphanSnapshotGeoRef->__invoke($previousGeoRefId, $entity->entity_id);
        }

        return response()->json([
            'snapshot' => self::buildSnapshotData($snapshot),
        ]);
    }

    /**
     * Delete a snapshot.
     */
    public function destroy(
        Entity $entity,
        GeometrySnapshot $snapshot,
        DeleteSnapshotAction $deleteSnapshot,
    ): JsonResponse {
        $this->authorizeSnapshotBelongsToEntity($snapshot, $entity);

        $deleteSnapshot($snapshot);

        return response()->json(null, 204);
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    /**
     * Build the serialisable snapshot array for JSON responses.
     *
     * @return array<string, mixed>
     */
    private static function buildSnapshotData(GeometrySnapshot $snapshot): array
    {
        return [
            'snapshot_id' => $snapshot->snapshot_id,
            'entity_id' => $snapshot->entity_id,
            'geo_ref_id' => $snapshot->geo_ref_id,
            'year_start' => $snapshot->year_start,
            'year_end' => $snapshot->year_end,
            'label' => $snapshot->label,
            'confidence' => $snapshot->confidence?->value,
            'notes' => $snapshot->notes,
            'description' => $snapshot->description,
            'display_priority' => $snapshot->display_priority,
            'source_citations' => $snapshot->source_citations,
            'relationship_id' => $snapshot->relationship_id,
            'source_event_id' => $snapshot->source_event_id,
            'geojson' => $snapshot->geom,
            'territory_geojson' => $snapshot->territory_geom,
            'geo_ref' => $snapshot->geoRef !== null
                ? [
                    'geo_ref_id' => $snapshot->geoRef->geo_ref_id,
                    'provider' => $snapshot->geoRef->provider?->value,
                    'external_type' => $snapshot->geoRef->external_type?->value,
                    'external_id' => $snapshot->geoRef->external_id,
                    'match_role' => $snapshot->geoRef->match_role?->value,
                    'retrieval_method' => $snapshot->geoRef->retrieval_method?->value,
                    'match_score' => $snapshot->geoRef->match_score !== null ? (float) $snapshot->geoRef->match_score : null,
                    'source_meta' => $snapshot->geoRef->source_meta,
                ]
                : null,
            'created_at' => $snapshot->created_at?->toISOString(),
            'updated_at' => $snapshot->updated_at?->toISOString(),
        ];
    }

    /**
     * @param  array<string, mixed>  $validated
     * @return array<string, mixed>
     */
    private function prepareSnapshotPayload(
        array $validated,
        Entity $entity,
        PrepareGeoRefAttachmentAction $prepareGeoRefAttachment,
        CreateEntityGeoRefAction $createEntityGeoRef,
    ): array {
        $reference = $validated['geography_reference'] ?? null;
        unset($validated['geography_reference']);

        if (! is_array($reference)) {
            return $validated;
        }

        $prepared = $prepareGeoRefAttachment->__invoke($reference);
        $geoRef = $createEntityGeoRef->__invoke($entity, $prepared['attributes']);
        $validated['geo_ref_id'] = $geoRef->geo_ref_id;

        if (! isset($validated['geojson']) && ! isset($validated['territory_geojson']) && is_array($prepared['geojson'])) {
            $geometryType = $prepared['geojson']['type'] ?? null;

            if (in_array($geometryType, ['Polygon', 'MultiPolygon'], true)) {
                $validated['territory_geojson'] = $prepared['geojson'];
            } else {
                $validated['geojson'] = $prepared['geojson'];
            }
        }

        if (! isset($validated['geojson']) && ! isset($validated['territory_geojson'])) {
            throw ValidationException::withMessages([
                'geojson' => 'At least one geometry (geojson or territory_geojson) must be provided.',
            ]);
        }

        return $validated;
    }

    /**
     * Abort 404 if the snapshot does not belong to the given entity.
     */
    private function authorizeSnapshotBelongsToEntity(GeometrySnapshot $snapshot, Entity $entity): void
    {
        if ($snapshot->entity_id !== $entity->entity_id) {
            abort(404);
        }
    }
}
