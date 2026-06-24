<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Actions\Timeline\ProjectEntityTimelineAction;
use App\Console\Commands\BackfillEntityCommand;
use App\Models\Entity;
use App\Models\GeometryPeriod;

/**
 * Backfill the canonical derived tables for a single entity and rebuild its
 * timeline.
 *
 * This is the per-entity unit of work shared by {@see BackfillEntityCommand}
 * (which loops it over every entity) and the admin "Backfill" action on the
 * entity editor. The most common interactive use is turning a freshly-set
 * primary location into territory {@see GeometryPeriod} rows, which
 * is what the public map reads — a primary location alone is invisible on the
 * map until those geometry periods are derived.
 */
class BackfillEntityAction
{
    public function __construct(
        private readonly BackfillAliasesAction $aliases,
        private readonly BackfillTagsAction $tags,
        private readonly BackfillTemporalRangesAction $temporalRanges,
        private readonly BackfillLocationsAction $locations,
        private readonly BackfillGeometryPeriodsAction $geometryPeriods,
        private readonly ProjectEntityTimelineAction $timeline,
    ) {}

    /**
     * @return array{aliases:int,tags:int,temporal_ranges:int,locations:int,geometry_periods:int}
     */
    public function __invoke(Entity $entity): array
    {
        // Reload without global scopes + the relations the sub-actions read, so
        // this works regardless of how the caller fetched the entity (route
        // model binding applies the default scope; the command eager-loads).
        $entity = Entity::query()
            ->withoutGlobalScopes()
            ->with(['aliases', 'entityTags', 'primaryTemporalRange', 'primaryLocation'])
            ->findOrFail($entity->getKey());

        $counts = [
            'aliases' => ($this->aliases)($entity),
            'tags' => ($this->tags)($entity),
            'temporal_ranges' => ($this->temporalRanges)($entity),
            'locations' => ($this->locations)($entity),
            'geometry_periods' => ($this->geometryPeriods)($entity),
        ];

        ($this->timeline)((string) $entity->entity_id);

        return $counts;
    }
}
