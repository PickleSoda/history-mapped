<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Timeline\ProjectEntityTimelineAction;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;

class RebuildEntityTimelineJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(
        public readonly string $entityId,
    ) {}

    public function handle(ProjectEntityTimelineAction $project): void
    {
        $project->rebuildForEntity($this->entityId);
    }
}
