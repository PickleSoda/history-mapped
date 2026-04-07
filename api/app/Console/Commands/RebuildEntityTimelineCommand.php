<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Timeline\ProjectEntityTimelineAction;
use Illuminate\Console\Command;

class RebuildEntityTimelineCommand extends Command
{
    protected $signature = 'timeline:rebuild {entity_id? : Optional entity UUID for targeted rebuild}';

    protected $description = 'Rebuild materialized entity timeline entries from geometry periods';

    public function handle(ProjectEntityTimelineAction $project): int
    {
        $entityId = $this->argument('entity_id');

        $count = $project($entityId !== null ? (string) $entityId : null);

        if ($entityId !== null) {
            $this->info("Rebuilt timeline for entity {$entityId}: {$count} entries");
        } else {
            $this->info("Rebuilt timelines for all entities: {$count} entries");
        }

        return self::SUCCESS;
    }
}
