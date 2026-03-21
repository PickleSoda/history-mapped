<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Entity\CreateEntityAction;
use App\DTOs\EntityData;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Import a single entity from a pipeline JSONL record.
 *
 * Validates the record, converts it to EntityData, calls CreateEntityAction,
 * and stores _relationship_hints in a staging table for later resolution.
 */
class ImportEntityJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;

    public int $backoff = 10;

    /**
     * @param  array<string, mixed>  $record  — Decoded JSONL entity record.
     * @param  string  $batchId  — Pipeline batch identifier.
     */
    public function __construct(
        public readonly array $record,
        public readonly string $batchId,
    ) {}

    public function handle(): void
    {
        $record = $this->record;
        $name = $record['name'] ?? 'unknown';

        try {
            // ── Pre-flight dedup (belt-and-suspenders) ──────────────────
            if ($this->alreadyExists($record)) {
                Log::info("[Pipeline] Skipped duplicate: {$name} ({$record['wikidata_id'] ?? 'no QID'})");

                return;
            }

            // ── Validate minimum required fields ────────────────────────
            if (! isset($record['name'], $record['entity_type'], $record['entity_group'])) {
                Log::warning("[Pipeline] Skipped record missing required fields: ".json_encode(array_keys($record)));

                return;
            }

            // ── Strip pipeline-only fields before creating EntityData ───
            $relationshipHints = $record['_relationship_hints'] ?? [];
            $rawInfobox = $record['attributes']['_infobox'] ?? null;

            $entityRecord = $record;
            unset($entityRecord['_relationship_hints']);

            if (isset($entityRecord['attributes']['_infobox'])) {
                unset($entityRecord['attributes']['_infobox']);
            }

            // ── Ensure pipeline_draft status ────────────────────────────
            $entityRecord['verification_status'] = 'pipeline_draft';

            // ── Build EntityData DTO ────────────────────────────────────
            $entityData = EntityData::fromArray($entityRecord);

            // ── Create entity ───────────────────────────────────────────
            $action = app(CreateEntityAction::class);
            $entity = $action($entityData, "pipeline:{$this->batchId}");

            Log::info("[Pipeline] Imported: {$name} → {$entity->entity_id}");

            // ── Stage relationship hints for later resolution ───────────
            if (! empty($relationshipHints)) {
                $this->stageRelationshipHints($entity->entity_id, $relationshipHints);
            }

        } catch (\Throwable $e) {
            Log::error("[Pipeline] Failed to import {$name}: {$e->getMessage()}", [
                'record' => array_diff_key($record, array_flip(['_relationship_hints'])),
                'exception' => $e->getTraceAsString(),
            ]);

            throw $e;
        }
    }

    /**
     * Check if the entity already exists by wikidata_id.
     */
    private function alreadyExists(array $record): bool
    {
        $wikidataId = $record['wikidata_id'] ?? null;

        return $wikidataId && DB::table('entities')
            ->where('wikidata_id', $wikidataId)
            ->exists();
    }

    /**
     * Store relationship hints for later batch resolution.
     *
     * Uses a lightweight staging table. If the table doesn't exist,
     * falls back to the entity's attributes JSONB.
     */
    private function stageRelationshipHints(string $entityId, array $hints): void
    {
        // Try staging table first
        try {
            foreach ($hints as $hint) {
                DB::table('pipeline_relationship_hints')->insert([
                    'source_entity_id' => $entityId,
                    'relationship_type' => $hint['relationship_type'],
                    'target_wikidata_id' => $hint['target_wikidata_id'],
                    'target_label' => $hint['target_label'] ?? null,
                    'confidence' => $hint['confidence'] ?? 'medium',
                    'wikidata_property' => $hint['source'] ?? null,
                    'batch_id' => $this->batchId,
                    'resolved' => false,
                    'created_at' => now(),
                ]);
            }
        } catch (\Throwable $e) {
            // Fallback: store hints in entity attributes
            Log::debug("[Pipeline] Staging table not available, storing hints in attributes: {$e->getMessage()}");

            DB::table('entities')
                ->where('entity_id', $entityId)
                ->update([
                    'attributes' => DB::raw(
                        "jsonb_set(COALESCE(attributes, '{}'::jsonb), '{_relationship_hints}', '".
                        json_encode($hints)."'::jsonb)"
                    ),
                ]);
        }
    }
}
