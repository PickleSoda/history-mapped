<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\RelationshipData;
use App\Http\Api\V1\Requests\StoreRelationshipRequest;
use App\Http\Api\V1\Resources\RelationshipResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class EntityRelationshipController extends Controller
{
    /**
     * GET /api/v1/entities/{entity}/relationships
     *
     * List all relationships for an entity (both outgoing and incoming).
     */
    public function index(string $entity): AnonymousResourceCollection
    {
        $entityModel = Entity::where('entity_id', $entity)->firstOrFail();

        $relationships = EntityRelationship::query()
            ->where('source_entity_id', $entityModel->entity_id)
            ->orWhere('target_entity_id', $entityModel->entity_id)
            ->with(['sourceEntity', 'targetEntity'])
            ->orderBy('created_at', 'desc')
            ->get();

        return RelationshipResource::collection($relationships);
    }

    /**
     * POST /api/v1/entities/{entity}/relationships
     *
     * Create a new relationship where this entity is the source.
     */
    public function store(
        string $entity,
        StoreRelationshipRequest $request,
        CreateRelationshipAction $action,
    ): JsonResponse {
        // Verify the source entity exists
        Entity::where('entity_id', $entity)->firstOrFail();

        $data = RelationshipData::fromArray(
            array_merge(
                ['source_entity_id' => $entity],
                $request->validated(),
            ),
        );

        $relationship = $action($data, $request->user()?->id);

        return (new RelationshipResource($relationship->load(['sourceEntity', 'targetEntity'])))
            ->response()
            ->setStatusCode(201);
    }

    /**
     * DELETE /api/v1/entities/{entity}/relationships/{relationship}
     */
    public function destroy(string $entity, string $relationship): JsonResponse
    {
        $rel = EntityRelationship::where('relationship_id', $relationship)
            ->where(function ($q) use ($entity) {
                $q->where('source_entity_id', $entity)
                    ->orWhere('target_entity_id', $entity);
            })
            ->firstOrFail();

        $rel->delete();

        return response()->json(null, 204);
    }
}
