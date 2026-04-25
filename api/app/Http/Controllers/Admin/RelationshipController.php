<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Relationship\CreateRelationshipAction;
use App\Actions\Relationship\CreateDerivedPresencePeriodAction;
use App\DTOs\RelationshipData;
use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreRelationshipRequest;
use App\Http\Requests\Admin\UpdateRelationshipRequest;
use App\Jobs\RebuildEntityTimelineJob;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
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
                    ]),
                'targetEntity.primaryLocation',
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
                    ]),
                'sourceEntity.primaryLocation',
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

        $this->syncDerivedPresencePeriods(
            $relationship,
            app(CreateDerivedPresencePeriodAction::class),
            (string) $request->user()->id,
        );

        RebuildEntityTimelineJob::dispatch($relationship->source_entity_id);

        $relationship->load([
            'targetEntity' => fn ($query) => $query
                ->withoutGlobalScopes()
                ->select([
                    'entity_id',
                    'name',
                    'entity_type',
                    'entity_group',
                    'verification_status',
                ]),
            'targetEntity.primaryLocation',
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

        $sourceEntityId = $relationship->source_entity_id;
        $relationship->delete();

        RebuildEntityTimelineJob::dispatch($sourceEntityId);

        return response()->json(null, 204);
    }

    /**
     * Update an existing outgoing relationship.
     */
    public function update(
        UpdateRelationshipRequest $request,
        Entity $entity,
        EntityRelationship $relationship,
        CreateDerivedPresencePeriodAction $createDerivedPresencePeriod,
    ): JsonResponse {
        if ($relationship->source_entity_id !== $entity->entity_id) {
            abort(404);
        }

        $validated = $request->validated();
        $updates = [];

        foreach (['target_entity_id', 'relationship_type', 'temporal_start', 'temporal_end', 'description', 'confidence', 'derive_geometry_period'] as $field) {
            if (array_key_exists($field, $validated)) {
                $updates[$field] = $validated[$field];
            }
        }

        // Keep explicit year columns in sync for update payloads so DB constraints remain valid.
        if (array_key_exists('temporal_start', $validated)) {
            $updates['start_year'] = self::extractYear($validated['temporal_start']);
        }

        if (array_key_exists('temporal_end', $validated)) {
            $updates['end_year'] = self::extractYear($validated['temporal_end']);
        }

        $relationship->update($updates);
        $relationship->refresh();

        $this->syncDerivedPresencePeriods(
            $relationship,
            $createDerivedPresencePeriod,
            (string) $request->user()->id,
        );

        RebuildEntityTimelineJob::dispatch($relationship->source_entity_id);

        $relationship->load([
            'targetEntity' => fn ($query) => $query
                ->withoutGlobalScopes()
                ->select([
                    'entity_id',
                    'name',
                    'entity_type',
                    'entity_group',
                    'verification_status',
                ]),
            'targetEntity.primaryLocation',
        ]);

        return response()->json([
            'relationship' => self::buildRelationshipData($relationship, 'outgoing'),
        ]);
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
                'geojson' => $relatedEntity->primaryLocation?->geom,
                'territory_geojson' => $relatedEntity->primaryLocation?->territory_geom,
            ] : null,
            'derive_geometry_period' => (bool) $relationship->derive_geometry_period,
            'created_at' => $relationship->created_at?->toISOString(),
        ];
    }

    private function syncDerivedPresencePeriods(
        EntityRelationship $relationship,
        CreateDerivedPresencePeriodAction $createDerivedPresencePeriod,
        string $userId,
    ): void {
        $linkedDerivedPeriods = GeometryPeriod::query()
            ->where('relationship_id', $relationship->relationship_id)
            ->where('provenance_mode', 'derived');

        $typeValue = $relationship->relationship_type instanceof RelationshipType
            ? $relationship->relationship_type->value
            : (string) $relationship->relationship_type;

        $relationshipType = RelationshipType::from($typeValue);

        if (! $createDerivedPresencePeriod->supportsRelationshipType($relationshipType)) {
            $linkedDerivedPeriods->delete();

            return;
        }

        if (! $relationship->derive_geometry_period) {
            $linkedDerivedPeriods->delete();

            return;
        }

        $periodStartYear = $relationship->start_year;
        $periodEndYear = $relationship->end_year ?? $periodStartYear;

        if ($periodStartYear === null || $periodEndYear === null) {
            $linkedDerivedPeriods->delete();

            return;
        }

        if ($linkedDerivedPeriods->exists()) {
            $linkedDerivedPeriods->update([
                'start_year' => $periodStartYear,
                'end_year' => $periodEndYear,
                'description' => $relationship->description,
            ]);

            return;
        }

        $data = new RelationshipData(
            sourceEntityId: $relationship->source_entity_id,
            targetEntityId: $relationship->target_entity_id,
            relationshipType: $relationshipType,
            temporalStart: $relationship->temporal_start,
            temporalEnd: $relationship->temporal_end,
            description: $relationship->description,
            confidence: $relationship->confidence,
            sourceCitations: $relationship->source_citations,
            deriveGeometryPeriod: true,
        );

        $createDerivedPresencePeriod($relationship, $data, $userId);
    }

    private static function extractYear(mixed $value): ?int
    {
        if (! is_string($value) || trim($value) === '') {
            return null;
        }

        if (preg_match('/^-?\d+/', trim($value), $matches) !== 1) {
            return null;
        }

        return (int) $matches[0];
    }
}
