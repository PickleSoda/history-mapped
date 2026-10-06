<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\EntityReferenceResolver;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Import relationships produced by the agent pipeline.
 *
 * Each record names its ends (source_name / target_name) and, when the pipeline
 * knows them, carries their identity too: source_entity_id / target_entity_id
 * (an existing DB row) and source_wikidata_id / target_wikidata_id (the QID the
 * entity was imported with). Each end resolves identity-first via
 * EntityReferenceResolver: entity_id -> wikidata_id -> exact name ->
 * case-insensitive name -> unique alternative name. For relation types that
 * imply both ends existed at the relation's date (rules, fought_at, …) the
 * QID / name / alias matches are date-guarded: a namesake of another era is
 * never linked, and an end with only such namesakes (or several dated ones)
 * stays unresolved as 'namesake_ambiguous'. Identity matters because
 * the entity import dedups by QID, so the row can carry a different name than
 * the label ("Tell Halaf" imported into the existing "Guzana" row).
 *
 * Legacy files carry no ids; --entities-file (the run's entities_to_create.jsonl)
 * backfills each end's wikidata_id by name. Existing (source,target,type) rows
 * are skipped, so re-running over old artifacts only ADDS missing relations;
 * --additive-recovery resolves each end by name first (exactly what the
 * original name-keyed import did) and uses ids only where the name finds
 * nothing, so a re-run never re-points a record the old import already linked
 * (no parallel copies) and only fills the gaps.
 *
 * Records that cannot be resolved (entity missing) or carry an invalid
 * relationship_type are reported but do not abort the batch. A non-zero exit is
 * returned only on a genuine insert exception, so the pipeline can distinguish
 * "nothing matched" (a data gap) from "the import broke" (a fault).
 *
 * Usage:
 *   php artisan pipeline:import-relations storage/app/pipeline/.../relations.jsonl --batch-id=run_123
 *   php artisan pipeline:import-relations <run>/relations.jsonl --entities-file=<run>/entities_to_create.jsonl
 */
class ImportRelationsCommand extends Command
{
    protected $signature = 'pipeline:import-relations
        {path : Path to a relations JSONL file}
        {--batch-id= : Custom batch identifier (default: auto-generated)}
        {--force : Insert even if an identical (source,target,type) relationship exists}
        {--entities-file= : Entities JSONL whose name -> wikidata_id backfills ends that carry no ids (legacy relations.jsonl)}
        {--additive-recovery : Re-run mode: resolve ends by name first (legacy behaviour) and fall back to ids only where the name finds nothing}';

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
        $additiveRecovery = (bool) $this->option('additive-recovery');

        $validTypes = $this->validRelationshipTypes();
        $resolver = new EntityReferenceResolver;

        $qidByName = [];
        $entitiesFile = $this->option('entities-file');
        if (is_string($entitiesFile) && $entitiesFile !== '') {
            $entitiesPath = str_starts_with($entitiesFile, '/') ? $entitiesFile : base_path($entitiesFile);
            if (! is_file($entitiesPath)) {
                $this->error("Entities file not found: {$entitiesFile}");

                return self::FAILURE;
            }
            $qidByName = $this->qidIndex($entitiesPath);
        }

        /** @var array<string, string> $unresolvedNames name => reason */
        $unresolvedNames = [];
        /** @var array<string, int> $resolvedVia */
        $resolvedVia = [];

        $created = 0;
        $skipped = 0;
        $unresolved = 0;
        $invalid = 0;
        $failed = 0;
        $selfLoops = 0;

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

            // Namesake guard: a contemporaneous relation's dates must fit each
            // end's lifespan ('Philip II rules Spain 1556' is never the
            // Macedonian); see EntityReferenceResolver::pickNamesake.
            $span = EntityReferenceResolver::relationSpan($type, $record['start_date'] ?? null, $record['end_date'] ?? null);
            $source = $this->resolveEnd($resolver, $record, 'source', $sourceName, $qidByName, $additiveRecovery, $span);
            $target = $this->resolveEnd($resolver, $record, 'target', $targetName, $qidByName, $additiveRecovery, $span);

            foreach ([[$sourceName, $source], [$targetName, $target]] as [$endName, $end]) {
                if ($end['id'] === null) {
                    $unresolvedNames[$endName] ??= (string) $end['reason'];
                } else {
                    $resolvedVia[$end['via']] = ($resolvedVia[$end['via']] ?? 0) + 1;
                }
            }

            $sourceId = $source['id'];
            $targetId = $target['id'];

            if ($sourceId === null || $targetId === null) {
                $unresolved++;

                continue;
            }

            // Two labels can collapse onto one row (QID dedup); never write a
            // self-loop.
            if ($sourceId === $targetId) {
                $selfLoops++;

                continue;
            }

            try {
                if (! $force && $this->relationshipExists($sourceId, $targetId, $type)) {
                    $skipped++;

                    continue;
                }

                // Persist the provenance the pipeline gathered (source event,
                // endpoint Wikidata ids, transcript run) rather than a bare stub;
                // always stamp batch_id/created_by so the import remains traceable.
                $citations = is_array($record['source_citations'] ?? null) ? $record['source_citations'] : [];
                $citations += ['created_by' => 'historical-agent-pipeline'];
                $citations['batch_id'] = $batchId;

                DB::table('relationships')->insert([
                    'source_entity_id' => $sourceId,
                    'target_entity_id' => $targetId,
                    'relationship_type' => $type,
                    'temporal_start' => $this->stringField($record, 'start_date'),
                    'temporal_end' => $this->stringField($record, 'end_date'),
                    'description' => $this->stringField($record, 'description'),
                    'confidence' => $this->normalizeConfidence($record['confidence'] ?? null),
                    'source_citations' => json_encode($citations),
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
            'self_loops' => $selfLoops,
            'unresolved_names' => count($unresolvedNames),
            'resolved_via' => $resolvedVia,
        ]));

        if ($unresolvedNames !== []) {
            // Compact per-run list: every endpoint that matched nothing, with why.
            $this->line('RELATION_UNRESOLVED '.json_encode(
                array_map(
                    static fn (string $name, string $reason): string => "{$name} ({$reason})",
                    array_keys($unresolvedNames),
                    array_values($unresolvedNames),
                ),
                JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
        }

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }

    /**
     * Resolve one end of a relation record, identity first — or, in
     * additive-recovery mode, name first with identity as the fallback.
     *
     * @param  array<string, mixed>  $record
     * @param  array<string, string>  $qidByName  lowercased name => wikidata_id (from --entities-file)
     * @param  array{0: int, 1: int}|null  $span  the relation's years when its type implies both ends existed then
     * @return array{id: string|null, via: string, reason: string|null}
     */
    private function resolveEnd(
        EntityReferenceResolver $resolver,
        array $record,
        string $side,
        string $name,
        array $qidByName,
        bool $nameFirst = false,
        ?array $span = null,
    ): array {
        if ($nameFirst) {
            $byName = $resolver->resolve(null, null, $name, $span);
            if ($byName['id'] !== null) {
                return $byName;
            }
        }

        $wikidataId = $this->stringField($record, "{$side}_wikidata_id")
            ?? ($qidByName[mb_strtolower($name)] ?? null);

        return $resolver->resolve(
            $this->stringField($record, "{$side}_entity_id"),
            $wikidataId,
            $name,
            $span,
        );
    }

    /**
     * name (lowercased) => wikidata_id for every record in an entities JSONL.
     * Only primary names: relation ends are candidate labels, and indexing
     * aliases could hand a held-for-review namesake another entity's QID.
     *
     * @return array<string, string>
     */
    private function qidIndex(string $path): array
    {
        $index = [];

        foreach ($this->readJsonl($path) as $record) {
            $qid = $this->stringField($record, 'wikidata_id');
            $name = $this->stringField($record, 'name');
            if ($qid !== null && $name !== null) {
                $index[mb_strtolower($name)] = $qid;
            }
        }

        return $index;
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
