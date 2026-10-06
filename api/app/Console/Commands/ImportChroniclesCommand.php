<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Chronicle\EnrichChronicleMetadataAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Services\EntityReferenceResolver;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Import chronicle artifacts (JSON) produced by the agent pipeline.
 *
 * Usage:
 *   php artisan chronicles:import output/agent_runs/run_id/chronicle.json
 *   php artisan chronicles:import output/agent_runs/ --all
 *   php artisan chronicles:import output/agent_runs/run_id/chronicle.json --dry-run
 *   php artisan chronicles:import output/agent_runs/run_id/chronicle.json --link-missing
 *
 * Secondary entities resolve identity-first (EntityReferenceResolver):
 * entity_id uuid -> wikidata_id -> exact name -> case-insensitive name -> unique
 * alternative name. Legacy refs that carry the label in entity_id still work.
 *
 * --link-missing is the additive repair mode: for an EXISTING chronicle it only
 * attaches secondary entities missing from entries matched by identical
 * narrative_text. It never creates or deletes chronicles/entries/links and does
 * not touch chronicle metadata.
 */
class ImportChroniclesCommand extends Command
{
    protected $signature = 'chronicles:import
        {path : Path to a chronicle JSON file or directory}
        {--all : Import all chronicle.json files in the directory}
        {--force : Overwrite existing chronicles (match by slug)}
        {--dry-run : Show what would be imported without writing}
        {--sync : Process synchronously (default: sync for import command)}
        {--link-missing : Additive repair: only attach missing secondary entities to existing entries}';

    protected $description = 'Import chronicle artifacts from the agent pipeline into the database';

    private ?EntityReferenceResolver $resolver = null;

    /** @var array<string, string> ref => reason, for refs that matched no entity */
    private array $unresolvedRefs = [];

    public function handle(): int
    {
        $path = $this->argument('path');
        $isAll = (bool) $this->option('all');
        $force = (bool) $this->option('force');
        $dryRun = (bool) $this->option('dry-run');
        $linkMissing = (bool) $this->option('link-missing');

        if ($linkMissing && $force) {
            $this->error('--link-missing is additive and cannot be combined with --force.');

            return self::FAILURE;
        }

        $files = $this->resolveFiles($path, $isAll);

        if (empty($files)) {
            $this->error("No chronicle.json files found at: {$path}");

            return self::FAILURE;
        }

        $this->info('Files: '.count($files));
        if ($dryRun) {
            $this->warn('DRY RUN MODE — no changes will be written.');
        }
        if ($force) {
            $this->warn('Force mode: existing chronicles will be overwritten.');
        }
        $this->newLine();

        $totalChronicles = 0;
        $totalEntries = 0;
        $totalSkipped = 0;
        $totalFailed = 0;

        foreach ($files as $file) {
            $this->components->twoColumnDetail(basename($file), 'Processing...');

            $data = $this->readJson($file);

            if ($data === null) {
                $this->warn('  Skipped: invalid or empty JSON.');
                $totalSkipped++;

                continue;
            }

            if ($dryRun) {
                $this->outputDryRun($data, $file);
                $totalChronicles++;
                $totalEntries += count($data['entries'] ?? []);

                continue;
            }

            try {
                $result = $linkMissing
                    ? $this->linkMissingEntities($data)
                    : $this->importChronicle($data, $force);
                $totalChronicles++;
                $totalEntries += $result['entries_imported'];

                $this->components->twoColumnDetail(
                    basename($file),
                    "<fg=green>{$result['status']}</> ({$result['entries_imported']} entries)",
                );
            } catch (\Throwable $e) {
                $this->error("  Failed to import {$file}: {$e->getMessage()}");
                Log::error('Chronicle import failed', ['file' => $file, 'error' => $e->getMessage()]);
                $totalFailed++;
            }
        }

        $this->newLine();
        $this->info("Chronicles: {$totalChronicles} imported, {$totalSkipped} skipped, {$totalFailed} failed");
        $this->info("Total entries imported: {$totalEntries}");

        if ($this->unresolvedRefs !== []) {
            $this->line('CHRONICLE_UNRESOLVED '.json_encode(
                array_map(
                    static fn (string $ref, string $reason): string => "{$ref} ({$reason})",
                    array_keys($this->unresolvedRefs),
                    array_values($this->unresolvedRefs),
                ),
                JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
        }

        // Non-zero exit on real failure so the pipeline does not report false
        // success (e.g. an invalid-UUID primary_relationship_id raising 22P02).
        return $totalFailed > 0 ? self::FAILURE : self::SUCCESS;
    }

    /**
     * Resolve the input path to a list of chronicle JSON files.
     *
     * @return list<string>
     */
    private function resolveFiles(string $path, bool $all): array
    {
        $fullPath = str_starts_with($path, '/') || (strlen($path) > 1 && $path[1] === ':')
            ? $path
            : base_path($path);

        if (is_file($fullPath) && basename($fullPath) === 'chronicle.json') {
            return [$fullPath];
        }

        if (is_dir($fullPath) && $all) {
            $files = glob(rtrim($fullPath, '/').'/**/chronicle.json') ?: [];

            return array_values($files);
        }

        if (is_dir($fullPath)) {
            $this->warn('Directory given but --all not set. Use --all to import all chronicle.json files.');

            return [];
        }

        return [];
    }

    /**
     * Read and decode a JSON file.
     */
    private function readJson(string $file): ?array
    {
        if (! file_exists($file) || ! is_readable($file)) {
            $this->error("Cannot read file: {$file}");

            return null;
        }

        $contents = file_get_contents($file);
        if ($contents === false) {
            $this->error("Cannot read file: {$file}");

            return null;
        }

        $data = json_decode($contents, true);

        if (json_last_error() !== JSON_ERROR_NONE) {
            $this->error("Invalid JSON in {$file}: ".json_last_error_msg());

            return null;
        }

        return $data;
    }

    /**
     * Output what would be imported (dry-run mode).
     */
    private function outputDryRun(array $data, string $file): void
    {
        $title = $data['title'] ?? 'Untitled';
        $slug = $data['slug'] ?? 'no-slug';
        $entryCount = count($data['entries'] ?? []);

        $this->line("  [DRY RUN] Would import: {$title} (slug: {$slug}, entries: {$entryCount})");
    }

    /**
     * Import a single chronicle with its entries.
     *
     * @return array{status: string, entries_imported: int}
     */
    private function importChronicle(array $data, bool $force): array
    {
        $slug = $data['slug'] ?? null;

        if (! $slug) {
            throw new \RuntimeException('Chronicle missing "slug" field.');
        }

        $existing = Chronicle::where('slug', $slug)->first();

        if ($existing && ! $force) {
            // Update the existing chronicle in place
            return $this->updateExistingChronicle($existing, $data);
        }

        return DB::transaction(function () use ($data, $slug, $existing, $force) {
            if ($existing && $force) {
                // Delete old entries before re-importing
                ChronicleEntry::where('chronicle_id', $existing->chronicle_id)->delete();
                $chronicle = $existing;
            } else {
                $chronicle = new Chronicle;
                $chronicle->chronicle_id = Str::uuid()->toString();
            }

            $chronicle->title = $data['title'] ?? 'Untitled Chronicle';
            $chronicle->slug = $slug;
            $chronicle->source_type = $data['source_type'] ?? 'video_transcript';
            $chronicle->source_reference = $data['source_reference'] ?? null;
            $chronicle->status = $data['status'] ?? 'draft';
            $chronicle->start_year = $data['start_year'] ?? null;
            $chronicle->end_year = $data['end_year'] ?? null;
            $chronicle->impact_score = $data['impact_score'] ?? null;
            $chronicle->approximate_location = $data['approximate_location'] ?? null;
            $chronicle->metadata = $data['metadata'] ?? [];
            $chronicle->save();

            $entriesImported = $this->importEntries($chronicle, $data['entries'] ?? []);

            // Derive impact_score / approximate_location (and backfill years)
            // from the now-attached relationships + entities.
            app(EnrichChronicleMetadataAction::class)($chronicle);

            $status = $existing ? 'updated' : 'created';

            return ['status' => $status, 'entries_imported' => $entriesImported];
        });
    }

    /**
     * Update an existing chronicle without deleting (preserves created_at).
     *
     * @return array{status: string, entries_imported: int}
     */
    private function updateExistingChronicle(Chronicle $chronicle, array $data): array
    {
        // In non-force mode, just update metadata but don't replace entries
        $chronicle->title = $data['title'] ?? $chronicle->title;
        $chronicle->source_type = $data['source_type'] ?? $chronicle->source_type;
        $chronicle->source_reference = $data['source_reference'] ?? $chronicle->source_reference;
        $chronicle->status = $data['status'] ?? $chronicle->status;
        $chronicle->start_year = $data['start_year'] ?? $chronicle->start_year;
        $chronicle->end_year = $data['end_year'] ?? $chronicle->end_year;
        $chronicle->impact_score = $data['impact_score'] ?? $chronicle->impact_score;
        $chronicle->approximate_location = $data['approximate_location'] ?? $chronicle->approximate_location;
        $chronicle->metadata = $data['metadata'] ?? $chronicle->metadata;
        $chronicle->save();

        return ['status' => 'skipped (use --force to replace entries)', 'entries_imported' => 0];
    }

    /**
     * Import chronicle entries and their secondary entities.
     */
    private function importEntries(Chronicle $chronicle, array $entries): int
    {
        $imported = 0;

        foreach ($entries as $entryData) {
            $entry = new ChronicleEntry;
            $entry->entry_id = Str::uuid()->toString();
            $entry->chronicle_id = $chronicle->chronicle_id;
            $entry->sequence_order = $entryData['sequence_order'] ?? $imported;
            $entry->primary_relationship_id = $entryData['primary_relationship_id'] ?? null;
            $entry->narrative_text = $entryData['narrative_text'] ?? '';
            $entry->notes = $entryData['notes'] ?? null;
            $entry->start_year = $entryData['start_year'] ?? null;
            $entry->end_year = $entryData['end_year'] ?? null;
            $entry->impact_score = $entryData['impact_score'] ?? null;
            $entry->approximate_location = $entryData['approximate_location'] ?? null;
            $entry->source_evidence = $entryData['source_evidence'] ?? null;
            $entry->save();

            // Sync secondary entities
            $this->syncSecondaryEntities($entry, $entryData['secondary_entities'] ?? []);

            $imported++;
        }

        return $imported;
    }

    /**
     * Additive repair for an existing chronicle: attach the file's secondary
     * entities that are missing from the matching DB entries (same chronicle,
     * identical narrative_text — sequence_order breaks ties). Never creates or
     * deletes anything else.
     *
     * @return array{status: string, entries_imported: int}
     */
    private function linkMissingEntities(array $data): array
    {
        $slug = $data['slug'] ?? null;
        if (! $slug) {
            throw new \RuntimeException('Chronicle missing "slug" field.');
        }

        $chronicle = Chronicle::where('slug', $slug)->first();
        if ($chronicle === null) {
            return ['status' => 'not found (link-missing never creates)', 'entries_imported' => 0];
        }

        $byText = [];
        foreach (ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->get() as $entry) {
            $byText[(string) $entry->narrative_text][] = $entry;
        }

        $linked = 0;
        $unmatched = 0;

        DB::transaction(function () use ($data, $byText, &$linked, &$unmatched): void {
            foreach ($data['entries'] ?? [] as $entryData) {
                $candidates = $byText[(string) ($entryData['narrative_text'] ?? '')] ?? [];
                if (count($candidates) > 1) {
                    $seq = $entryData['sequence_order'] ?? null;
                    $candidates = array_values(array_filter(
                        $candidates,
                        static fn (ChronicleEntry $e): bool => $e->sequence_order === $seq,
                    ));
                }
                if (count($candidates) !== 1) {
                    $unmatched++;

                    continue;
                }

                $linked += $this->syncSecondaryEntities($candidates[0], $entryData['secondary_entities'] ?? [], onlyMissing: true);
            }
        });

        return [
            'status' => "links added: {$linked}".($unmatched > 0 ? ", unmatched entries: {$unmatched}" : ''),
            'entries_imported' => 0,
        ];
    }

    /**
     * Sync secondary entities for a chronicle entry.
     *
     * Each ref resolves identity-first via EntityReferenceResolver: entity_id
     * (a uuid, or the label for legacy/unresolved refs) -> wikidata_id -> name
     * -> case-insensitive name -> unique alias; the QID / name / alias matches
     * are date-guarded by the entry's years (no namesake of another era). Unresolved refs are skipped with
     * a warning naming the reason. With $onlyMissing, pairs already linked are
     * left alone (additive repair). Returns the number of links attached.
     */
    private function syncSecondaryEntities(ChronicleEntry $entry, array $secondaryEntities, bool $onlyMissing = false): int
    {
        $this->resolver ??= new EntityReferenceResolver;
        $pivotData = [];
        $span = EntityReferenceResolver::yearSpan(
            is_numeric($entry->start_year) ? (int) $entry->start_year : null,
            is_numeric($entry->end_year) ? (int) $entry->end_year : null,
        );

        foreach ($secondaryEntities as $sec) {
            $ref = $sec['entity_id'] ?? null; // a UUID (resolved) or a name (fallback)
            $role = $sec['role'] ?? 'participant';
            $sequence = $sec['sequence_in_entry'] ?? null;
            $wikidataId = is_string($sec['wikidata_id'] ?? null) ? $sec['wikidata_id'] : null;
            $name = is_string($sec['name'] ?? null) ? $sec['name'] : null;

            if ((! is_string($ref) || $ref === '') && $wikidataId === null && $name === null) {
                continue;
            }

            // The entry's years guard name / QID matches against namesakes of
            // another era (EntityReferenceResolver::pickNamesake).
            $resolved = $this->resolver->resolve(is_string($ref) ? $ref : null, $wikidataId, $name, $span);

            if ($resolved['id'] === null) {
                $label = $name ?? (is_string($ref) && $ref !== '' ? $ref : (string) $wikidataId);
                $this->unresolvedRefs[$label] ??= (string) $resolved['reason'];
                $this->warn("  Entity not found: {$label} ({$resolved['reason']}; skipping secondary entity)");

                continue;
            }

            $pivotData[$resolved['id']] ??= [
                'role' => $role,
                'sequence_in_entry' => $sequence,
            ];
        }

        if ($onlyMissing && $pivotData !== []) {
            $existing = DB::table('chronicle_entry_entities')
                ->where('entry_id', $entry->entry_id)
                ->whereIn('entity_id', array_keys($pivotData))
                ->pluck('entity_id')
                ->all();
            foreach ($existing as $entityId) {
                unset($pivotData[(string) $entityId]);
            }
        }

        if (! empty($pivotData)) {
            $entry->secondaryEntities()->attach($pivotData);
        }

        return count($pivotData);
    }
}
