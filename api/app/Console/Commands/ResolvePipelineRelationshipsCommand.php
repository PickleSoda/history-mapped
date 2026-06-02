<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\ResolveRelationshipsJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ResolvePipelineRelationshipsCommand extends Command
{
    protected $signature = 'pipeline:resolve-relationships
        {batchId? : Resolve hints for this batch; omit to resolve all unresolved hints}
        {--sync : Run synchronously instead of dispatching a job}
        {--dry-run : Show counts without creating relationships}';

    protected $description = 'Resolve pipeline relationship hints into relationship records';

    public function handle(): int
    {
        $batchId = $this->argument('batchId');
        $sync = (bool) $this->option('sync');
        $dryRun = (bool) $this->option('dry-run');

        if ($dryRun) {
            return $this->runDryRun($batchId);
        }

        if ($batchId !== null) {
            return $this->resolveBatch((string) $batchId, $sync);
        }

        return $this->resolveAll($sync);
    }

    private function resolveBatch(string $batchId, bool $sync): int
    {
        $count = DB::table('pipeline_relationship_hints')
            ->where('batch_id', $batchId)
            ->where('resolved', false)
            ->count();

        if ($count === 0) {
            $this->warn("No unresolved hints for batch: {$batchId}");

            return self::SUCCESS;
        }

        $this->info("Resolving {$count} hints for batch: {$batchId}");

        $job = new ResolveRelationshipsJob($batchId);

        if ($sync) {
            app()->call([$job, 'handle']);
        } else {
            dispatch($job);
            $this->info('Job dispatched.');
        }

        return self::SUCCESS;
    }

    private function resolveAll(bool $sync): int
    {
        $batchIds = DB::table('pipeline_relationship_hints')
            ->where('resolved', false)
            ->distinct()
            ->pluck('batch_id');

        if ($batchIds->isEmpty()) {
            $this->warn('No unresolved hints found.');

            return self::SUCCESS;
        }

        $this->info("Resolving hints for {$batchIds->count()} batch(es)...");

        foreach ($batchIds as $batchId) {
            $job = new ResolveRelationshipsJob($batchId);

            if ($sync) {
                app()->call([$job, 'handle']);
            } else {
                dispatch($job);
            }
        }

        $this->info('Done.');

        return self::SUCCESS;
    }

    private function runDryRun(?string $batchId): int
    {
        $query = DB::table('pipeline_relationship_hints')
            ->select('batch_id', 'resolution_note', DB::raw('count(*) as total'))
            ->where('resolved', false);

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->groupBy('batch_id', 'resolution_note')->get();

        if ($rows->isEmpty()) {
            $this->warn('No unresolved hints found.');

            return self::SUCCESS;
        }

        $this->table(
            ['Batch', 'Resolution Note', 'Count'],
            $rows->map(fn ($r) => [$r->batch_id, $r->resolution_note, $r->total])->toArray()
        );

        return self::SUCCESS;
    }
}