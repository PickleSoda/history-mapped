<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\RelationshipData;
use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreRelationshipRequest;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Http\JsonResponse;

/**
 * JSON controller for relationship CRUD on the entity edit page.
 *
 * Lives under the auth+verified middleware group (web routes).
 * Returns JSON so the RelationshipPanel can communicate via fetch.
 */
class RelationshipController extends Controller
{
    /**
     * List all relationships (outgoing + incoming) for an entity.
     */
    public function index(Entity $entity): JsonResponse
    {
        $outgoing = $entity->outgoingRelationships()
            ->with([
                'targetEntity' => fn ($query) => $query
                    ->withoutGlobalScopes()
                    ->select([
                        'entity_id',
                        'name',
                        'entity_type',
                        'entity_group',
                        'verification_status',
                        'geom',
                        'territory_geom',
                    ]),
            ])
            ->get();

        $incoming = $entity->incomingRelationships()
            ->with([
                'sourceEntity' => fn ($query) => $query
                    ->withoutGlobalScopes()
                    ->select([
                        'entity_id',
                        'name',
                        'entity_type',
                        'entity_group',
                        'verification_status',
                        'geom',
                        'territory_geom',
                    ]),
            ])
            ->get();

        return response()->json([
            'outgoing' => $outgoing->map(fn (EntityRelationship $r) => self::buildRelationshipData($r, 'outgoing')),
            'incoming' => $incoming->map(fn (EntityRelationship $r) => self::buildRelationshipData($r, 'incoming')),
        ]);
    }

    /**
     * Create a new relationship from the given entity to a target entity.
     */
    public function store(
        StoreRelationshipRequest $request,
        Entity $entity,
        CreateRelationshipAction $createRelationship,
    ): JsonResponse {
        $validated = $request->validated();
        $validated['source_entity_id'] = $entity->entity_id;

        $data = RelationshipData::fromArray($validated);
        $relationship = $createRelationship($data, (string) $request->user()->id);

        $relationship->load([
            'targetEntity' => fn ($query) => $query
                ->withoutGlobalScopes()
                ->select([
                    'entity_id',
                    'name',
                    'entity_type',
                    'entity_group',
                    'verification_status',
                    'geom',
                    'territory_geom',
                ]),
        ]);

        return response()->json([
            'relationship' => self::buildRelationshipData($relationship, 'outgoing'),
        ], 201);
    }

    /**
     * Delete a relationship.
     *
     * Only relationships where the route entity is the source may be deleted here.
     * Incoming relationships are deleted via their source entity's edit page.
     */
    public function destroy(Entity $entity, EntityRelationship $relationship): JsonResponse
    {
        if ($relationship->source_entity_id !== $entity->entity_id) {
            abort(404);
        }

        $relationship->delete();

        return response()->json(null, 204);
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    /**
     * Build the serialisable relationship array for JSON responses.
     *
     * @param  'outgoing'|'incoming'  $direction
     * @return array<string, mixed>
     */
    private static function buildRelationshipData(EntityRelationship $relationship, string $direction): array
    {
        $relatedEntity = $direction === 'outgoing'
            ? $relationship->targetEntity
            : $relationship->sourceEntity;

        return [
            'relationship_id' => $relationship->relationship_id,
            'source_entity_id' => $relationship->source_entity_id,
            'target_entity_id' => $relationship->target_entity_id,
            'relationship_type' => $relationship->relationship_type instanceof RelationshipType
                ? $relationship->relationship_type->value
                : $relationship->relationship_type,
            'temporal_start' => $relationship->temporal_start,
            'temporal_end' => $relationship->temporal_end,
            'start_year' => $relationship->start_year,
            'end_year' => $relationship->end_year,
            'description' => $relationship->description,
            'confidence' => $relationship->confidence instanceof ConfidenceLevel
                ? $relationship->confidence->value
                : $relationship->confidence,
            'direction' => $direction,
            'related_entity' => $relatedEntity ? [
                'id' => $relatedEntity->entity_id,
                'name' => $relatedEntity->name,
                'entity_type' => $relatedEntity->entity_type?->value,
                'entity_group' => $relatedEntity->entity_group?->value,
                'verification_status' => $relatedEntity->verification_status?->value,
                'geojson' => $relatedEntity->geom,
                'territory_geojson' => $relatedEntity->territory_geom,
            ] : null,
            'created_at' => $relationship->created_at?->toISOString(),
        ];
    }
}
