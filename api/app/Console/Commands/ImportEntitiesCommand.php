<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\ImportEntityJob;
use App\Jobs\ResolveRelationshipsJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;

/**
 * Import entities from pipeline-generated JSONL files.
 *
 * Reads JSONL files (one entity per line) produced by the Python pipeline
 * and dispatches ImportEntityJob for each record. After all entities are
 * imported, dispatches ResolveRelationshipsJob to resolve _relationship_hints
 * into proper relationship records.
 *
 * Usage:
 *   php artisan pipeline:import storage/app/pipeline/political_entity.jsonl
 *   php artisan pipeline:import storage/app/pipeline/ --all
 *   php artisan pipeline:import storage/app/pipeline/political_entity.jsonl --sync
 */
class ImportEntitiesCommand extends Command
{
    protected $signature = 'pipeline:import
        {path : Path to a JSONL file or directory}
        {--all : Import all .jsonl files in the directory}
        {--sync : Process synchronously instead of dispatching jobs}
        {--force : Overwrite existing entities instead of skipping duplicates}
        {--skip-dedup : Skip database deduplication check}
        {--skip-relationships : Skip relationship resolution after import}
        {--batch-id= : Custom batch identifier (default: auto-generated)}
        {--chunk=100 : Number of records per job dispatch}';

    protected $description = 'Import entities from pipeline JSONL files into the database';

    /**
     * Reference table type markers set by the pipeline.
     * Records tagged with any of these are silently skipped — they belong
     * in curated reference tables, not the entities table.
     */
    private const REF_TYPES = [
        'ref_historical_period',
        'ref_geographic_region',
        'ref_body_of_water',
        'ref_calendar_system',
        'ref_writing_system',
        'ref_measurement_unit',
    ];

    public function handle(): int
    {
        $path = $this->argument('path');
        $isAll = (bool) $this->option('all');

        // Resolve files
        $files = $this->resolveFiles($path, $isAll);

        if (empty($files)) {
            $this->error("No .jsonl files found at: {$path}");

            return self::FAILURE;
        }

        $batchId = $this->option('batch-id') ?? 'pipeline-'.now()->format('Ymd-His');
        $chunkSize = (int) $this->option('chunk');
        $sync = (bool) $this->option('sync');
        $skipDedup = (bool) $this->option('skip-dedup');
        $force = (bool) $this->option('force');

        $this->info("Batch: {$batchId}");
        $this->info('Files: '.count($files));
        if ($force) {
            $this->warn('Force mode: existing entities will be overwritten.');
        }
        $this->newLine();

        $totalImported = 0;
        $totalSkipped = 0;

        foreach ($files as $file) {
            $this->components->twoColumnDetail(basename($file), 'Processing…');

            $lines = $this->readJsonl($file);
            $lineCount = count($lines);

            if ($lineCount === 0) {
                $this->warn('  Empty file, skipping.');

                continue;
            }

            $imported = 0;
            $skipped = 0;
            $bar = $this->output->createProgressBar($lineCount);

            foreach (array_chunk($lines, $chunkSize) as $chunk) {
                foreach ($chunk as $record) {
                    // Skip reference-table items (eras, regions, bodies of water, etc.)
                    if ($this->isRefTableItem($record)) {
                        $skipped++;
                        $bar->advance();

                        continue;
                    }

                    // Pre-import dedup: check wikidata_id
                    if (! $force && ! $skipDedup && $this->isDuplicate($record)) {
                        $skipped++;
                        $bar->advance();

                        continue;
                    }

                    if ($sync) {
                        $this->importSync($record, $batchId, $force);
                    } else {
                        ImportEntityJob::dispatch($record, $batchId, $force);
                    }

                    $imported++;
                    $bar->advance();
                }
            }

            $bar->finish();
            $this->newLine();
            $this->components->twoColumnDetail(
                basename($file),
                "<fg=green>{$imported} imported</> | <fg=yellow>{$skipped} skipped (dedup)</>"
            );

            $totalImported += $imported;
            $totalSkipped += $skipped;
        }

        $this->newLine();
        $this->info("Total: {$totalImported} imported, {$totalSkipped} skipped");

        // Dispatch relationship resolution
        if (! $this->option('skip-relationships')) {
            $this->info('Dispatching relationship resolution job…');
            if ($sync) {
                (new ResolveRelationshipsJob($batchId))->handle();
            } else {
                ResolveRelationshipsJob::dispatch($batchId);
            }
        }

        return self::SUCCESS;
    }

    /**
     * Check if a record is a reference-table item that should not be imported
     * as a regular entity.
     */
    private function isRefTableItem(array $record): bool
    {
        // Explicit ref_type marker from the pipeline
        if (isset($record['_ref_type']) && in_array($record['_ref_type'], self::REF_TYPES, true)) {
            return true;
        }

        return false;
    }

    /**
     * Resolve the input path to a list of JSONL files.
     *
     * Skips `*_ref.jsonl` and `*_untyped.jsonl` files (reference-table items
     * and unclassified items are not regular entities).
     *
     * @return list<string>
     */
    private function resolveFiles(string $path, bool $all): array
    {
        $fullPath = base_path($path);

        if (is_file($fullPath) && str_ends_with($fullPath, '.jsonl')) {
            return [$fullPath];
        }

        if (is_dir($fullPath) && $all) {
            $files = glob($fullPath.'/*.jsonl') ?: [];

            // Exclude ref and untyped files from batch imports
            $files = array_filter($files, function (string $file) {
                $basename = basename($file);

                return ! str_ends_with($basename, '_ref.jsonl')
                    && ! str_ends_with($basename, '_untyped.jsonl');
            });

            return array_values($files);
        }

        if (is_dir($fullPath)) {
            $this->warn('Directory given but --all not set. Use --all to import all files.');

            return [];
        }

        return [];
    }

    /**
     * Read a JSONL file into an array of decoded records.
     *
     * @return list<array<string, mixed>>
     */
    private function readJsonl(string $file): array
    {
        $records = [];
        $handle = fopen($file, 'r');

        if (! $handle) {
            $this->error("Cannot open file: {$file}");

            return [];
        }

        $lineNum = 0;
        while (($line = fgets($handle)) !== false) {
            $lineNum++;
            $line = trim($line);

            if ($line === '') {
                continue;
            }

            $decoded = json_decode($line, true);

            if (json_last_error() !== JSON_ERROR_NONE) {
                $this->warn("  Invalid JSON at line {$lineNum}, skipping");

                continue;
            }

            $records[] = $decoded;
        }

        fclose($handle);

        return $records;
    }

    /**
     * Check if an entity already exists (by wikidata_id or exact name + type).
     */
    private function isDuplicate(array $record): bool
    {
        $wikidataId = $record['wikidata_id'] ?? null;

        if ($wikidataId) {
            return DB::table('entities')
                ->where('wikidata_id', $wikidataId)
                ->exists();
        }

        // Fallback: exact name + type match
        $name = $record['name'] ?? null;
        $type = $record['entity_type'] ?? null;

        if ($name && $type) {
            return DB::table('entities')
                ->where('name', $name)
                ->where('entity_type', $type)
                ->exists();
        }

        return false;
    }

    /**
     * Import a single record synchronously (for --sync mode).
     */
    private function importSync(array $record, string $batchId, bool $force = false): void
    {
        try {
            $job = new ImportEntityJob($record, $batchId, $force);
            $job->handle();
        } catch (\Throwable $e) {
            $this->error("  Failed to import {$record['name']}: {$e->getMessage()}");
        }
    }
}
