<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\EntityGeoRef\CreateEntityGeoRefAction;
use App\Actions\EntityGeoRef\PrepareGeoRefAttachmentAction;
use App\Actions\EntityGeoRef\PruneOrphanSnapshotGeoRefAction;
use App\Actions\GeometrySnapshot\CreateSnapshotAction;
use App\Actions\GeometrySnapshot\DeleteSnapshotAction;
use App\Actions\GeometrySnapshot\ListSnapshotsAction;
use App\Actions\GeometrySnapshot\UpdateSnapshotAction;
use App\DTOs\GeometrySnapshotData;
use App\Http\Api\V1\Requests\StoreGeometrySnapshotRequest;
use App\Http\Api\V1\Requests\UpdateGeometrySnapshotRequest;
use App\Http\Api\V1\Resources\GeometrySnapshotResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\ValidationException;

class GeometrySnapshotController extends Controller
{
    /**
     * GET /api/v1/entities/{entity}/geometry-snapshots
     */
    public function index(Entity $entity, ListSnapshotsAction $listSnapshots): AnonymousResourceCollection
    {
        return GeometrySnapshotResource::collection($listSnapshots($entity));
    }

    /**
     * GET /api/v1/entities/{entity}/geometry-snapshots/at/{year}
     */
    public function atYear(Entity $entity, int $year): GeometrySnapshotResource
    {
        $snapshot = $entity->geometrySnapshots()
            ->where('year_start', '<=', $year)
            ->where('year_end', '>=', $year)
            ->reorder()
            ->orderByDesc('display_priority')
            ->orderBy('year_start')
            ->firstOrFail();

        return new GeometrySnapshotResource($snapshot);
    }

    /**
     * POST /api/v1/entities/{entity}/geometry-snapshots
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
        $snapshot = $createSnapshot($data, (string) $request->user()?->id);

        return (new GeometrySnapshotResource($snapshot))
            ->response()
            ->setStatusCode(201);
    }

    /**
     * PUT /api/v1/entities/{entity}/geometry-snapshots/{snapshot}
     */
    public function update(
        UpdateGeometrySnapshotRequest $request,
        Entity $entity,
        string $snapshot,
        UpdateSnapshotAction $updateSnapshot,
        PrepareGeoRefAttachmentAction $prepareGeoRefAttachment,
        CreateEntityGeoRefAction $createEntityGeoRef,
        PruneOrphanSnapshotGeoRefAction $pruneOrphanSnapshotGeoRef,
    ): GeometrySnapshotResource {
        $model = GeometrySnapshot::query()
            ->where('snapshot_id', $snapshot)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();
        $previousGeoRefId = $model->geo_ref_id;

        $validated = $this->prepareSnapshotPayload(
            $request->validated(),
            $entity,
            $prepareGeoRefAttachment,
            $createEntityGeoRef,
        );
        $merged = array_merge([
            'entity_id' => $model->entity_id,
            'year_start' => $model->year_start,
            'year_end' => $model->year_end,
            'display_priority' => $model->display_priority,
            'geo_ref_id' => $model->geo_ref_id,
        ], $validated);

        $data = GeometrySnapshotData::fromArray($merged);
        $updatedSnapshot = $updateSnapshot($model, $data);

        if ($previousGeoRefId !== $updatedSnapshot->geo_ref_id) {
            $pruneOrphanSnapshotGeoRef->__invoke($previousGeoRefId, $entity->entity_id);
        }

        return new GeometrySnapshotResource($updatedSnapshot);
    }

    /**
     * DELETE /api/v1/entities/{entity}/geometry-snapshots/{snapshot}
     */
    public function destroy(
        Entity $entity,
        string $snapshot,
        DeleteSnapshotAction $deleteSnapshot,
    ): JsonResponse {
        $model = GeometrySnapshot::query()
            ->where('snapshot_id', $snapshot)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();

        $deleteSnapshot($model);

        return response()->json(null, 204);
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
}
