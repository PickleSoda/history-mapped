<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\ImportEntityJob;
use App\Jobs\ResolveRelationshipsJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ImportBorderRelationsCommand extends Command
{
    protected $signature = 'pipeline:import-border-relations
        {path : Directory containing ohm_relation_entities.jsonl and ohm_relation_hints.jsonl}
        {--sync : Process synchronously instead of dispatching jobs}
        {--force : Overwrite existing entities}
        {--skip-resolve : Skip relationship resolution after staging hints}
        {--batch-id= : Custom batch identifier (default: auto-generated)}';

    protected $description = 'Import OHM relation entities and stage relation hints for resolution';

    public function handle(): int
    {
        $path = (string) $this->argument('path');
        $fullPath = str_starts_with($path, '/') || (strlen($path) > 1 && $path[1] === ':')
            ? $path
            : base_path($path);

        if (! is_dir($fullPath)) {
            $this->error("Directory not found: {$path}");

            return self::FAILURE;
        }

        $entitiesPath = rtrim($fullPath, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.'ohm_relation_entities.jsonl';
        $hintsPath = rtrim($fullPath, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.'ohm_relation_hints.jsonl';

        if (! is_file($entitiesPath) || ! is_file($hintsPath)) {
            $this->error('Expected ohm_relation_entities.jsonl and ohm_relation_hints.jsonl in the given directory.');

            return self::FAILURE;
        }

        $batchId = (string) ($this->option('batch-id') ?: 'border-relations-'.now()->format('Ymd-His'));
        $sync = (bool) $this->option('sync');
        $force = (bool) $this->option('force');
        $skipResolve = (bool) $this->option('skip-resolve');

        $importedEntities = $this->importEntities($entitiesPath, $batchId, $sync, $force);
        [$stagedHints, $skippedHints, $unresolvedSources] = $this->stageHints($hintsPath, $batchId);

        if (! $skipResolve) {
            if ($sync) {
                app()->call([new ResolveRelationshipsJob($batchId), 'handle']);
            } else {
                ResolveRelationshipsJob::dispatch($batchId);
            }
        }

        $this->info("Batch: {$batchId}");
        $this->info("Entities imported: {$importedEntities}");
        $this->info("Hints staged: {$stagedHints}");
        $this->info("Hints skipped: {$skippedHints}");
        $this->info("Hints unresolved-source: {$unresolvedSources}");
        if ($skipResolve) {
            $this->info('Relationship resolution skipped.');
        }

        return self::SUCCESS;
    }

    private function importEntities(string $entitiesPath, string $batchId, bool $sync, bool $force): int
    {
        $count = 0;

        foreach ($this->readJsonl($entitiesPath) as $record) {
            if ($sync) {
                (new ImportEntityJob($record, $batchId, $force))->handle();
            } else {
                ImportEntityJob::dispatch($record, $batchId, $force);
            }

            $count++;
        }

        return $count;
    }

    /**
     * @return array{0:int,1:int,2:int}
     */
    private function stageHints(string $hintsPath, string $batchId): array
    {
        $staged = 0;
        $skipped = 0;
        $unresolvedSources = 0;

        foreach ($this->readJsonl($hintsPath) as $hint) {
            $sourceWikidataId = $hint['source_wikidata_id'] ?? null;
            if (! is_string($sourceWikidataId) || $sourceWikidataId === '') {
                $unresolvedSources++;

                continue;
            }

            $sourceEntityId = DB::table('entities')
                ->where('wikidata_id', $sourceWikidataId)
                ->value('entity_id');

            if (! is_string($sourceEntityId) || $sourceEntityId === '') {
                $unresolvedSources++;

                continue;
            }

            $normalizedProperty = $this->normalizeSourceProperty($hint['source'] ?? null);
            $relationshipType = $hint['relationship_type'] ?? null;
            $targetWikidataId = $hint['target_wikidata_id'] ?? null;

            if (! is_string($relationshipType) || $relationshipType === '' || ! is_string($targetWikidataId) || $targetWikidataId === '') {
                $skipped++;

                continue;
            }

            $existing = DB::table('pipeline_relationship_hints')
                ->where('batch_id', $batchId)
                ->where('source_entity_id', $sourceEntityId)
                ->where('relationship_type', $relationshipType)
                ->where('target_wikidata_id', $targetWikidataId)
                ->where(function ($query) use ($hint): void {
                    $temporalStart = $hint['temporal_start'] ?? null;
                    if ($temporalStart === null) {
                        $query->whereNull('temporal_start');
                    } else {
                        $query->where('temporal_start', $temporalStart);
                    }
                })
                ->where(function ($query) use ($hint): void {
                    $temporalEnd = $hint['temporal_end'] ?? null;
                    if ($temporalEnd === null) {
                        $query->whereNull('temporal_end');
                    } else {
                        $query->where('temporal_end', $temporalEnd);
                    }
                })
                ->exists();

            if ($existing) {
                $skipped++;

                continue;
            }

            DB::table('pipeline_relationship_hints')->insert([
                'source_entity_id' => $sourceEntityId,
                'relationship_type' => $relationshipType,
                'target_wikidata_id' => $targetWikidataId,
                'target_label' => $hint['target_label'] ?? null,
                'temporal_start' => $hint['temporal_start'] ?? null,
                'temporal_end' => $hint['temporal_end'] ?? null,
                'confidence' => $hint['confidence'] ?? 'medium',
                'wikidata_property' => $normalizedProperty,
                'batch_id' => $batchId,
                'resolved' => false,
                'created_at' => now(),
            ]);

            $staged++;
        }

        return [$staged, $skipped, $unresolvedSources];
    }

    private function normalizeSourceProperty(mixed $source): ?string
    {
        if (! is_string($source) || trim($source) === '') {
            return null;
        }

        $trimmed = trim($source);

        if (str_starts_with($trimmed, 'wikidata:')) {
            return substr($trimmed, strlen('wikidata:')) ?: null;
        }

        return $trimmed;
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function readJsonl(string $path): array
    {
        $records = [];
        $handle = fopen($path, 'r');

        if ($handle === false) {
            throw new \RuntimeException("Unable to open JSONL file: {$path}");
        }

        try {
            while (($line = fgets($handle)) !== false) {
                $line = trim($line);
                if ($line === '') {
                    continue;
                }

                $decoded = json_decode($line, true);
                if (is_array($decoded)) {
                    $records[] = $decoded;
                }
            }
        } finally {
            fclose($handle);
        }

        return $records;
    }
}
