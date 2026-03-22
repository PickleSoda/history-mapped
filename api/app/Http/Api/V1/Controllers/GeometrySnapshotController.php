<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

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
    ): JsonResponse {
        $validated = $request->validated();
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
    ): GeometrySnapshotResource {
        $model = GeometrySnapshot::query()
            ->where('snapshot_id', $snapshot)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();

        $validated = $request->validated();
        $merged = array_merge([
            'entity_id' => $model->entity_id,
            'year_start' => $model->year_start,
            'year_end' => $model->year_end,
            'display_priority' => $model->display_priority,
        ], $validated);

        $data = GeometrySnapshotData::fromArray($merged);

        return new GeometrySnapshotResource($updateSnapshot($model, $data));
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
}
