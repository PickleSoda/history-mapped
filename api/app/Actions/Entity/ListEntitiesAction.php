<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\DTOs\EntityFilterData;
use App\Models\Entity;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;

/**
 * List entities with filtering, spatial/temporal queries, and pagination.
 *
 * Delegates all query building to EntityBuilder for type-safe, composable queries.
 */
class ListEntitiesAction
{
    /**
     * @return LengthAwarePaginator<Entity>
     */
    public function __invoke(EntityFilterData $filters): LengthAwarePaginator
    {
        $query = Entity::query()->withGeoJson();

        // ── Text search ──────────────────────────────────────
        if ($filters->search !== null && $filters->search !== '') {
            $query->search($filters->search);
        }

        // ── Type / Group filters ─────────────────────────────
        if ($filters->type !== null) {
            $query->ofType($filters->type);
        }

        if ($filters->types !== null && $filters->types !== []) {
            $query->ofTypes($filters->types);
        }

        if ($filters->groups !== null && $filters->groups !== []) {
            $query->ofGroups($filters->groups);
        } elseif ($filters->group !== null) {
            $query->ofGroup($filters->group);
        }

        // ── Verification / Confidence ────────────────────────
        if ($filters->status !== null) {
            $query->withStatus($filters->status);
        }

        if ($filters->minConfidence !== null) {
            $query->withMinConfidence($filters->minConfidence);
        }

        // ── Tags ─────────────────────────────────────────────
        if ($filters->tag !== null && $filters->tag !== '') {
            $query->hasTag($filters->tag);
        }

        // ── Spatial filters ──────────────────────────────────
        if ($filters->hasBbox()) {
            $query->inBbox(
                $filters->bboxMinLng,
                $filters->bboxMinLat,
                $filters->bboxMaxLng,
                $filters->bboxMaxLat,
            );
        }

        if ($filters->hasNearPoint()) {
            $query->nearPoint(
                $filters->nearLng,
                $filters->nearLat,
                $filters->nearRadius,
            );
        }

        // ── Temporal filters ─────────────────────────────────
        if ($filters->hasTimeRange()) {
            $query->inTimeRange($filters->temporalStart, $filters->temporalEnd);
        }

        if ($filters->existsAt !== null) {
            $query->existsAt($filters->existsAt);
        }

        // ── Hierarchy ────────────────────────────────────────
        if ($filters->parentId !== null) {
            $query->childrenOf($filters->parentId);
        }

        // ── Eager loading ────────────────────────────────────
        if ($filters->includeRelationships) {
            $query->with(['outgoingRelationships.targetEntity', 'incomingRelationships.sourceEntity']);
        }

        // ── Sorting ──────────────────────────────────────────
        match ($filters->sort) {
            'impact' => $query->orderByImpact(),
            'recent' => $query->orderByRecent(),
            'chronological' => $query->orderByChronological(),
            'name' => $query->orderBy('name'),
            'distance' => $filters->hasNearPoint()
                ? $query->orderByDistanceFrom($filters->nearLng, $filters->nearLat)
                : $query->orderByImpact(),
            default => $filters->search !== null
                ? $query            // Full-text search has its own relevance ranking
                : $query->orderByImpact(),
        };

        return $query->paginate(
            perPage: $filters->perPage,
            page: $filters->page,
        );
    }
}
