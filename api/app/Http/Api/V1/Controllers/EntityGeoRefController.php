<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\EntityGeoRef\AttachOhmGeoRefAction;
use App\Actions\EntityGeoRef\DeleteEntityGeoRefAction;
use App\Actions\EntityGeoRef\ListEntityGeoRefsAction;
use App\Http\Api\V1\Requests\StoreEntityGeoRefRequest;
use App\Http\Api\V1\Resources\EntityGeoRefResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Services\Ohm\OhmLookupService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class EntityGeoRefController extends Controller
{
    public function index(Entity $entity, ListEntityGeoRefsAction $action): AnonymousResourceCollection
    {
        return EntityGeoRefResource::collection($action($entity));
    }

    public function store(
        StoreEntityGeoRefRequest $request,
        Entity $entity,
        AttachOhmGeoRefAction $action,
    ): JsonResponse {
        $geoRef = $action->__invoke($entity, $request->validated());

        return (new EntityGeoRefResource($geoRef))
            ->response()
            ->setStatusCode(201);
    }

    public function search(
        Request $request,
        Entity $entity,
        OhmLookupService $lookupService,
    ): JsonResponse {
        $validated = $request->validate([
            'q' => ['required', 'string', 'min:2', 'max:255'],
            'location_name' => ['sometimes', 'nullable', 'string', 'max:255'],
        ]);

        $results = $lookupService->searchByName(
            (string) $validated['q'],
            isset($validated['location_name']) ? (string) $validated['location_name'] : null,
        );

        return response()->json([
            'data' => $results,
        ]);
    }

    public function destroy(
        Entity $entity,
        string $ref,
        DeleteEntityGeoRefAction $action,
    ): JsonResponse {
        $geoRef = EntityGeoRef::query()
            ->where('geo_ref_id', $ref)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();

        $action->__invoke($geoRef);

        return response()->json(null, 204);
    }
}
