<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\GenerateEntityEmbeddingJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Generate pgvector embeddings for entities.
 *
 * Uses OpenAI's text-embedding-3-small (1536 dimensions) to generate
 * semantic embeddings for entity search and similarity features.
 *
 * Usage:
 *   php artisan pipeline:embeddings --pending          # Entities missing embeddings
 *   php artisan pipeline:embeddings --all              # Regenerate all embeddings
 *   php artisan pipeline:embeddings --type=city        # Specific entity type
 *   php artisan pipeline:embeddings --reembed          # Force re-embed (model upgrade)
 */
class GenerateEmbeddingsCommand extends Command
{
    protected $signature = 'pipeline:embeddings
        {--pending : Only entities without embeddings}
        {--all : Regenerate all embeddings}
        {--type= : Filter by entity_type}
        {--group= : Filter by entity_group}
        {--reembed : Force re-embed even if embedding exists}
        {--model= : Override embedding model (default: config)}
        {--chunk=50 : Batch size for job dispatch}
        {--sync : Process synchronously}';

    protected $description = 'Generate pgvector embeddings for entities using OpenAI';

    public function handle(): int
    {
        $model = $this->option('model') ?? config('services.openai.embedding_model', 'text-embedding-3-small');
        $chunk = (int) $this->option('chunk');
        $sync = (bool) $this->option('sync');

        // Build query
        $query = DB::table('entities')->select('entity_id', 'name');

        if ($this->option('pending') && ! $this->option('reembed')) {
            $query->whereNull('embedding');
        }

        if ($this->option('reembed')) {
            $query->where(function ($q) use ($model) {
                $q->whereNull('embedding')
                    ->orWhere('embedding_version', '!=', $model);
            });
        }

        if ($type = $this->option('type')) {
            $query->where('entity_type', $type);
        }

        if ($group = $this->option('group')) {
            $query->where('entity_group', $group);
        }

        $total = $query->count();

        if ($total === 0) {
            $this->info('No entities need embedding generation.');

            return self::SUCCESS;
        }

        $this->info("Generating embeddings for {$total} entities (model: {$model})");
        $bar = $this->output->createProgressBar($total);

        $query->orderBy('entity_id')
            ->chunk($chunk, function ($entities) use ($model, $sync, $bar) {
                $entityIds = $entities->pluck('entity_id')->toArray();

                if ($sync) {
                    $job = new GenerateEntityEmbeddingJob($entityIds, $model);
                    $job->handle();
                } else {
                    GenerateEntityEmbeddingJob::dispatch($entityIds, $model);
                }

                $bar->advance(count($entityIds));
            });

        $bar->finish();
        $this->newLine();
        $this->info("Done. Dispatched embedding jobs for {$total} entities.");

        return self::SUCCESS;
    }
}
