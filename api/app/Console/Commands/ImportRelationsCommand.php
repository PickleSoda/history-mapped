<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Import name-keyed relationships produced by the agent pipeline.
 *
 * The agent emits relations between entities it has just imported, referenced
 * by NAME (e.g. {"source_name":"Alexander the Great","target_name":"Battle of
 * Issus","relationship_type":"victorious_at"}). It usually has no Wikidata QID
 * for either end, so the QID-keyed pipeline:import-border-relations command
 * drops every one of them. This command instead resolves each end by name to a
 * real entity_id and writes a relationships row with a real UUID, so the
 * chronicle's primary_relationship_id can point at it.
 *
 * Records that cannot be resolved (entity missing) or carry an invalid
 * relationship_type are reported but do not abort the batch. A non-zero exit is
 * returned only on a genuine insert exception, so the pipeline can distinguish
 * "nothing matched" (a data gap) from "the import broke" (a fault).
 *
 * Usage:
 *   php artisan pipeline:import-relations storage/app/pipeline/.../relations.jsonl --batch-id=run_123
 */
class ImportRelationsCommand extends Command
{
    protected $signature = 'pipeline:import-relations
        {path : Path to a relations JSONL file}
        {--batch-id= : Custom batch identifier (default: auto-generated)}
        {--force : Insert even if an identical (source,target,type) relationship exists}';

    protected $description = 'Import name-keyed relationships from a pipeline JSONL file into the relationships table';

    public function handle(): int
    {
        $path = (string) $this->argument('path');
        $fullPath = str_starts_with($path, '/') || (strlen($path) > 1 && $path[1] === ':')
            ? $path
            : base_path($path);

        if (! is_file($fullPath)) {
            $this->error("Relations file not found: {$path}");

            return self::FAILURE;
        }

        $batchId = (string) ($this->option('batch-id') ?: 'relations-'.now()->format('Ymd-His'));
        $force = (bool) $this->option('force');

        $validTypes = $this->validRelationshipTypes();

        $created = 0;
        $skipped = 0;
        $unresolved = 0;
        $invalid = 0;
        $failed = 0;

        foreach ($this->readJsonl($fullPath) as $record) {
            $sourceName = $this->stringField($record, 'source_name');
            $targetName = $this->stringField($record, 'target_name');
            $type = $this->stringField($record, 'relationship_type');

            if ($sourceName === null || $targetName === null || $type === null) {
                $invalid++;

                continue;
            }

            if (! in_array($type, $validTypes, true)) {
                $this->warn("  Invalid relationship_type '{$type}' ({$sourceName} -> {$targetName}), skipping");
                $invalid++;

                continue;
            }

            $sourceId = $this->resolveEntityId($sourceName);
            $targetId = $this->resolveEntityId($targetName);

            if ($sourceId === null || $targetId === null) {
                $unresolved++;

                continue;
            }

            try {
                if (! $force && $this->relationshipExists($sourceId, $targetId, $type)) {
                    $skipped++;

                    continue;
                }

                DB::table('relationships')->insert([
                    'source_entity_id' => $sourceId,
                    'target_entity_id' => $targetId,
                    'relationship_type' => $type,
                    'temporal_start' => $this->stringField($record, 'start_date'),
                    'temporal_end' => $this->stringField($record, 'end_date'),
                    'description' => $this->stringField($record, 'description'),
                    'confidence' => $this->normalizeConfidence($record['confidence'] ?? null),
                    'source_citations' => json_encode(['created_by' => 'historical-agent-pipeline', 'batch_id' => $batchId]),
                    'created_by' => "pipeline:{$batchId}",
                    'created_at' => now(),
                ]);

                $created++;
            } catch (\Throwable $e) {
                $failed++;
                $this->error("  Failed to insert {$sourceName} -{$type}-> {$targetName}: {$e->getMessage()}");
            }
        }

        $this->info("Batch: {$batchId}");
        $this->line('RELATION_IMPORT_SUMMARY '.json_encode([
            'created' => $created,
            'skipped' => $skipped,
            'unresolved' => $unresolved,
            'invalid' => $invalid,
            'failed' => $failed,
        ]));

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }

    /**
     * Resolve an entity name to its UUID. Exact match first, then a
     * case-insensitive fallback. Returns null when nothing matches.
     */
    private function resolveEntityId(string $name): ?string
    {
        $id = DB::table('entities')->where('name', $name)->value('entity_id');
        if (is_string($id) && $id !== '') {
            return $id;
        }

        $id = DB::table('entities')->whereRaw('LOWER(name) = LOWER(?)', [$name])->value('entity_id');

        return is_string($id) && $id !== '' ? $id : null;
    }

    private function relationshipExists(string $sourceId, string $targetId, string $type): bool
    {
        return DB::table('relationships')
            ->where('source_entity_id', $sourceId)
            ->where('target_entity_id', $targetId)
            ->where('relationship_type', $type)
            ->exists();
    }

    /**
     * The set of allowed relationship_type enum values, read from PostgreSQL so
     * it stays in lockstep with the migration's 76-value enum.
     *
     * @return list<string>
     */
    private function validRelationshipTypes(): array
    {
        $rows = DB::select(
            "SELECT e.enumlabel AS label
             FROM pg_enum e
             JOIN pg_type t ON t.oid = e.enumtypid
             WHERE t.typname = 'relationship_type'"
        );

        return array_map(static fn ($row): string => (string) $row->label, $rows);
    }

    private function normalizeConfidence(mixed $value): string
    {
        if (is_string($value) && in_array($value, ['high', 'medium', 'low', 'unresolved'], true)) {
            return $value;
        }

        if (is_numeric($value)) {
            $num = (float) $value;
            if ($num >= 0.8) {
                return 'high';
            }
            if ($num >= 0.5) {
                return 'medium';
            }

            return 'low';
        }

        return 'medium';
    }

    /**
     * @param  array<string, mixed>  $record
     */
    private function stringField(array $record, string $key): ?string
    {
        $value = $record[$key] ?? null;

        if (! is_string($value)) {
            return null;
        }

        $trimmed = trim($value);

        return $trimmed === '' ? null : $trimmed;
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
