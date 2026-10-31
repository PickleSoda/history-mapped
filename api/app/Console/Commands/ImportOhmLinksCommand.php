<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\EntityGeoRef\ImportOhmLinksAction;
use Illuminate\Console\Command;

class ImportOhmLinksCommand extends Command
{
    protected $signature = 'pipeline:import-ohm-links
        {path : Path to ohm_links.jsonl written by python -m pipeline ohm-links fetch}
        {--dry-run : Roll every chunk back and only report the counters}
        {--overwrite-years : Replace temporal years on existing OHM refs even when they are set}
        {--batch-id= : Custom batch identifier (default: auto-generated)}
        {--run-id= : Pipeline run id stored in source_meta.run_id (default: name of the directory holding path)}
        {--chunk='.ImportOhmLinksAction::DEFAULT_CHUNK.' : Records / Wikidata-id groups per transaction (each chunk commits on its own)}';

    protected $description = 'Fill temporal ranges and tags on OHM geo-refs and link OHM features to entities by Wikidata id';

    public function handle(ImportOhmLinksAction $import): int
    {
        $path = (string) $this->argument('path');

        if (! is_file($path)) {
            $this->error("File not found: {$path}");

            return self::FAILURE;
        }

        $chunk = filter_var($this->option('chunk'), FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        if ($chunk === false) {
            $this->error('--chunk must be a positive integer');

            return self::FAILURE;
        }

        $dryRun = (bool) $this->option('dry-run');
        $batchId = $this->option('batch-id') ?? 'ohm-links-'.now()->format('Ymd-His');

        $this->info(($dryRun ? '[DRY-RUN] ' : '')."Batch: {$batchId}");

        $counters = $import($path, $batchId, $dryRun, (bool) $this->option('overwrite-years'), $this->option('run-id'), $chunk);

        $this->table(
            ['Counter', 'Value'],
            array_map(fn (string $name, int $value): array => [$name, $value], array_keys($counters), $counters),
        );

        return self::SUCCESS;
    }
}
