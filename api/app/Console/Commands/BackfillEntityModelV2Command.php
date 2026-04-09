<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\EntityModelV2\BackfillAliasesAction;
use App\Actions\EntityModelV2\BackfillGeometryPeriodsAction;
use App\Actions\EntityModelV2\BackfillLocationsAction;
use App\Actions\EntityModelV2\BackfillTagsAction;
use App\Actions\EntityModelV2\BackfillTemporalRangesAction;
use App\Actions\Timeline\ProjectEntityTimelineAction;
use App\Models\Entity;
use Illuminate\Console\Command;

class BackfillEntityModelV2Command extends Command
{
    protected $signature = 'entity-model-v2:backfill {--dry-run : Report changes without writing records} {--entity-id= : Backfill one entity id}';

    protected $description = 'Backfill Entity Model V2 canonical tables from legacy entity columns';

    public function handle(
        BackfillAliasesAction $aliasesAction,
        BackfillTagsAction $tagsAction,
        BackfillTemporalRangesAction $temporalRangesAction,
        BackfillLocationsAction $locationsAction,
        BackfillGeometryPeriodsAction $geometryPeriodsAction,
        ProjectEntityTimelineAction $timelineProjector,
    ): int {
        $dryRun = (bool) $this->option('dry-run');
        $singleEntityId = $this->option('entity-id');

        $query = Entity::query()->withoutGlobalScopes()->orderBy('entity_id');

        if (is_string($singleEntityId) && $singleEntityId !== '') {
            $query->where('entity_id', $singleEntityId);
        }

        $entities = $query->get();

        $counts = [
            'aliases' => 0,
            'tags' => 0,
            'temporal_ranges' => 0,
            'locations' => 0,
            'geometry_periods' => 0,
        ];

        foreach ($entities as $entity) {
            if ($dryRun) {
                $counts['aliases'] += is_array($entity->alternative_names) ? count($entity->alternative_names) : 0;
                $counts['tags'] += is_array($entity->tags) ? count(array_filter($entity->tags, fn ($tag) => is_string($tag) && trim($tag) !== '')) : 0;
                $counts['temporal_ranges'] += ($entity->temporal_start !== null || $entity->temporal_end !== null || $entity->temporal_start_year !== null || $entity->temporal_end_year !== null) ? 1 : 0;
                $counts['locations'] += ($entity->location_name !== null || $entity->geom !== null || $entity->territory_geom !== null) ? 1 : 0;

                continue;
            }

            $counts['aliases'] += $aliasesAction($entity);
            $counts['tags'] += $tagsAction($entity);
            $counts['temporal_ranges'] += $temporalRangesAction($entity);
            $counts['locations'] += $locationsAction($entity);
            $counts['geometry_periods'] += $geometryPeriodsAction($entity);
            $timelineProjector($entity->entity_id);
        }

        $mode = $dryRun ? 'DRY-RUN' : 'APPLIED';
        $this->info("[$mode] Entity Model V2 backfill summary");
        $this->table(['table', 'rows'], [
            ['entity_aliases', (string) $counts['aliases']],
            ['entity_tags', (string) $counts['tags']],
            ['entity_temporal_ranges', (string) $counts['temporal_ranges']],
            ['entity_locations', (string) $counts['locations']],
            ['geometry_periods', (string) $counts['geometry_periods']],
        ]);

        return self::SUCCESS;
    }
}
