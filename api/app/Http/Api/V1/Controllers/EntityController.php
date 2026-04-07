<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\DeleteEntityAction;
use App\Actions\Entity\GetEntityAction;
use App\Actions\Entity\ListEntitiesAction;
use App\Actions\Entity\MapEntitiesAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\DTOs\EntityFilterData;
use App\Http\Api\V1\Requests\ListEntitiesRequest;
use App\Http\Api\V1\Requests\MapEntitiesRequest;
use App\Http\Api\V1\Requests\StoreEntityRequest;
use App\Http\Api\V1\Requests\UpdateEntityRequest;
use App\Http\Api\V1\Resources\EntityMapResource;
use App\Http\Api\V1\Resources\EntityResource;
use App\Http\Api\V1\Resources\EntitySummaryResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class EntityController extends Controller
{
    /**
     * GET /api/v1/entities
     *
     * List entities with filtering, spatial/temporal queries, and pagination.
     */
    public function index(
        ListEntitiesRequest $request,
        ListEntitiesAction $action,
    ): AnonymousResourceCollection {
        $filters = EntityFilterData::fromArray($request->validated());
        $entities = $action($filters);

        return EntitySummaryResource::collection($entities);
    }

    /**
     * GET /api/v1/entities/map
     *
     * Lightweight GeoJSON FeatureCollection for map rendering.
     */
    public function map(
        MapEntitiesRequest $request,
        MapEntitiesAction $action,
    ): JsonResponse {
        $result = $action($request->validated());
        $entities = $result['entities'];

        return response()->json([
            'type' => 'FeatureCollection',
            'features' => EntityMapResource::collection($entities),
            'entities' => EntityMapResource::collection($entities),
            'territories' => $result['territories']->map(static fn ($territory): array => [
                'id' => $territory->geometry_period_id,
                'entity_id' => $territory->entity_id,
                'start_year' => $territory->start_year,
                'end_year' => $territory->end_year,
                'period_type' => $territory->period_type,
                'provenance_mode' => $territory->provenance_mode,
                'geometry' => $territory->territory_geom,
            ])->values(),
        ]);
    }

    /**
     * GET /api/v1/entities/{entity}
     *
     * Single entity with full detail. Optionally include relationships.
     */
    public function show(
        string $entity,
        GetEntityAction $action,
    ): EntityResource {
        $with = [];

        if (request()->boolean('include_relationships')) {
            $with = ['outgoingRelationships.targetEntity', 'incomingRelationships.sourceEntity'];
        }

        if (request()->boolean('include_children')) {
            $with[] = 'children';
        }

        return new EntityResource($action($entity, $with));
    }

    /**
     * POST /api/v1/entities
     *
     * Create a new entity.
     */
    public function store(
        StoreEntityRequest $request,
        CreateEntityAction $action,
    ): EntityResource {
        $data = EntityData::fromArray($request->validated());
        $entity = $action($data, $request->user()?->id);

        return (new EntityResource($entity))
            ->response()
            ->setStatusCode(201)
            ->getOriginalContent();
    }

    /**
     * PUT /api/v1/entities/{entity}
     *
     * Update an existing entity. Supports partial updates.
     */
    public function update(
        string $entity,
        UpdateEntityRequest $request,
        UpdateEntityAction $action,
    ): EntityResource {
        $existing = Entity::where('entity_id', $entity)->firstOrFail();
        $data = EntityData::fromArray(
            array_merge(
                ['name' => $existing->name, 'entity_type' => $existing->entity_type->value, 'entity_group' => $existing->entity_group->value],
                $request->validated(),
            ),
        );

        return new EntityResource($action($existing, $data));
    }

    /**
     * DELETE /api/v1/entities/{entity}
     */
    public function destroy(
        string $entity,
        DeleteEntityAction $action,
    ): JsonResponse {
        $existing = Entity::where('entity_id', $entity)->firstOrFail();
        $action($existing);

        return response()->json(null, 204);
    }
}
