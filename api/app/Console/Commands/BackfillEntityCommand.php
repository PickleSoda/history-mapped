<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Entity\BackfillEntityAction;
use App\Models\Entity;
use Illuminate\Console\Command;

class BackfillEntityCommand extends Command
{
    protected $signature = 'entity:backfill {--dry-run : Report changes without writing records} {--entity-id= : Backfill one entity id}';

    protected $description = 'Backfill canonical entity tables and rebuild timeline entries';

    public function handle(
        BackfillEntityAction $backfillEntity,
    ): int {
        $dryRun = (bool) $this->option('dry-run');
        $singleEntityId = $this->option('entity-id');

        $query = Entity::query()
            ->withoutGlobalScopes()
            ->with(['aliases', 'entityTags', 'primaryTemporalRange', 'primaryLocation'])
            ->orderBy('entity_id');

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
                $counts['aliases'] += $entity->aliases->count();
                $counts['tags'] += $entity->entityTags->count();
                $counts['temporal_ranges'] += ($entity->primaryTemporalRange !== null) ? 1 : 0;
                $counts['locations'] += ($entity->primaryLocation !== null) ? 1 : 0;

                continue;
            }

            $result = $backfillEntity($entity);
            $counts['aliases'] += $result['aliases'];
            $counts['tags'] += $result['tags'];
            $counts['temporal_ranges'] += $result['temporal_ranges'];
            $counts['locations'] += $result['locations'];
            $counts['geometry_periods'] += $result['geometry_periods'];
        }

        $mode = $dryRun ? 'DRY-RUN' : 'APPLIED';
        $this->info("[$mode] Entity backfill summary");
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
