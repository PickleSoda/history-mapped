<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ReportPipelineRelationshipHintsCommand extends Command
{
    protected $signature = 'pipeline:report-relationship-hints
        {batchId? : Report for this batch only; omit for all batches}
        {--limit=10 : Sample size per class}';

    protected $description = 'Report pipeline relationship hint status';

    public function handle(): int
    {
        $batchId = $this->argument('batchId');
        $limit = (int) $this->option('limit');

        $this->reportSummary($batchId);
        $this->reportRetryableSamples($batchId, $limit);
        $this->reportEmbeddedHints($limit);

        return self::SUCCESS;
    }

    private function reportSummary(?string $batchId): void
    {
        $query = DB::table('pipeline_relationship_hints')
            ->select('batch_id', 'resolution_note', DB::raw('count(*) as total'))
            ->groupBy('batch_id', 'resolution_note');

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->get();

        if ($rows->isEmpty()) {
            $this->warn('No hints found.');

            return;
        }

        $this->info('Summary by batch and resolution note:');
        $this->table(
            ['Batch', 'Resolution Note', 'Count'],
            $rows->map(fn ($r) => [$r->batch_id, $r->resolution_note, $r->total])->toArray()
        );
    }

    private function reportRetryableSamples(?string $batchId, int $limit): void
    {
        $query = DB::table('pipeline_relationship_hints')
            ->where('resolved', false)
            ->where('resolution_note', 'target_not_found')
            ->limit($limit);

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->get();

        if ($rows->isEmpty()) {
            return;
        }

        $this->newLine();
        $this->info("Retryable samples (target_not_found, limit {$limit}):");

        foreach ($rows as $row) {
            $sourceName = DB::table('entities')->where('entity_id', $row->source_entity_id)->value('name');
            $this->line("  - {$row->target_wikidata_id} (source: {$sourceName}) → type: {$row->relationship_type}");
        }
    }

    private function reportEmbeddedHints(int $limit): void
    {
        $entities = DB::table('entities')
            ->whereRaw('jsonb_exists(attributes, ?)', ['_relationship_hints'])
            ->select('entity_id', 'name', 'attributes')
            ->limit($limit)
            ->get();

        if ($entities->isEmpty()) {
            return;
        }

        $this->newLine();
        $this->info('Embedded hints still in attributes:');

        foreach ($entities as $entity) {
            $attrs = json_decode($entity->attributes, true) ?? [];
            $hintCount = count($attrs['_relationship_hints'] ?? []);
            $this->line("  - Entity: {$entity->name} ({$entity->entity_id}) → {$hintCount} hint(s)");
        }
    }
}