<?php

declare(strict_types=1);

namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Resolve pipeline relationship hints into actual relationship records.
 *
 * After entities are imported, this job reads the pipeline_relationship_hints
 * staging table and creates relationship records by matching target_wikidata_id
 * to existing entities.
 *
 * Dedup strategy for relationships:
 * - Unique on (source_entity_id, target_entity_id, relationship_type)
 * - Symmetric relationships (married_to, allied_with, etc.) check both directions
 * - Temporal overlap is NOT checked (two entities can have the same relationship
 *   type at different time periods — e.g., allied then at war)
 */
class ResolveRelationshipsJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 1;

    public int $timeout = 600;

    public function __construct(
        public readonly string $batchId,
    ) {}

    public function handle(): void
    {
        Log::info("[Pipeline] Resolving relationships for batch: {$this->batchId}");

        // First try the staging table approach
        if ($this->hasStagingTable()) {
            $this->resolveFromStagingTable();
        } else {
            $this->resolveFromEntityAttributes();
        }
    }

    /**
     * Check if the staging table exists.
     */
    private function hasStagingTable(): bool
    {
        try {
            return DB::getSchemaBuilder()->hasTable('pipeline_relationship_hints');
        } catch (\Throwable) {
            return false;
        }
    }

    /**
     * Resolve from the dedicated staging table.
     */
    private function resolveFromStagingTable(): void
    {
        $hints = DB::table('pipeline_relationship_hints')
            ->where('batch_id', $this->batchId)
            ->where('resolved', false)
            ->get();

        Log::info("[Pipeline] Found {$hints->count()} unresolved relationship hints");

        $created = 0;
        $skipped = 0;
        $unresolvable = 0;

        foreach ($hints as $hint) {
            // Look up target entity by wikidata_id
            $targetEntity = DB::table('entities')
                ->where('wikidata_id', $hint->target_wikidata_id)
                ->select('entity_id')
                ->first();

            if (! $targetEntity) {
                $unresolvable++;
                DB::table('pipeline_relationship_hints')
                    ->where('source_entity_id', $hint->source_entity_id)
                    ->where('target_wikidata_id', $hint->target_wikidata_id)
                    ->where('relationship_type', $hint->relationship_type)
                    ->update(['resolved' => true, 'resolution_note' => 'target_not_found']);

                continue;
            }

            // Dedup: check if this relationship already exists
            if ($this->relationshipExists(
                $hint->source_entity_id,
                $targetEntity->entity_id,
                $hint->relationship_type
            )) {
                $skipped++;
                DB::table('pipeline_relationship_hints')
                    ->where('source_entity_id', $hint->source_entity_id)
                    ->where('target_wikidata_id', $hint->target_wikidata_id)
                    ->where('relationship_type', $hint->relationship_type)
                    ->update(['resolved' => true, 'resolution_note' => 'already_exists']);

                continue;
            }

            // Self-reference guard
            if ($hint->source_entity_id === $targetEntity->entity_id) {
                $skipped++;

                continue;
            }

            // Create the relationship
            try {
                DB::table('relationships')->insert([
                    'relationship_id' => Str::uuid()->toString(),
                    'source_entity_id' => $hint->source_entity_id,
                    'target_entity_id' => $targetEntity->entity_id,
                    'relationship_type' => $hint->relationship_type,
                    'confidence' => $hint->confidence ?? 'medium',
                    'source_citations' => json_encode([[
                        'source_type' => 'reference',
                        'title' => "Wikidata property: {$hint->wikidata_property}",
                        'reliability' => 'reference',
                    ]]),
                    'created_by' => "pipeline:{$this->batchId}",
                    'created_at' => now(),
                ]);

                $created++;

                DB::table('pipeline_relationship_hints')
                    ->where('source_entity_id', $hint->source_entity_id)
                    ->where('target_wikidata_id', $hint->target_wikidata_id)
                    ->where('relationship_type', $hint->relationship_type)
                    ->update(['resolved' => true, 'resolution_note' => 'created']);

            } catch (\Throwable $e) {
                Log::warning("[Pipeline] Failed to create relationship: {$e->getMessage()}", [
                    'source' => $hint->source_entity_id,
                    'target' => $targetEntity->entity_id,
                    'type' => $hint->relationship_type,
                ]);
            }
        }

        Log::info("[Pipeline] Relationships resolved: {$created} created, {$skipped} skipped (dedup), {$unresolvable} unresolvable (target not in DB)");
    }

    /**
     * Fallback: resolve hints stored in entity attributes JSONB.
     */
    private function resolveFromEntityAttributes(): void
    {
        $entities = DB::table('entities')
            ->where('created_by', 'like', "pipeline:{$this->batchId}%")
            ->whereRaw("attributes ? '_relationship_hints'")
            ->select('entity_id', 'attributes')
            ->get();

        Log::info("[Pipeline] Found {$entities->count()} entities with embedded relationship hints");

        $created = 0;

        foreach ($entities as $entity) {
            $attributes = json_decode($entity->attributes, true) ?? [];
            $hints = $attributes['_relationship_hints'] ?? [];

            foreach ($hints as $hint) {
                $targetEntity = DB::table('entities')
                    ->where('wikidata_id', $hint['target_wikidata_id'] ?? null)
                    ->select('entity_id')
                    ->first();

                if (! $targetEntity || $entity->entity_id === $targetEntity->entity_id) {
                    continue;
                }

                if ($this->relationshipExists(
                    $entity->entity_id,
                    $targetEntity->entity_id,
                    $hint['relationship_type']
                )) {
                    continue;
                }

                try {
                    DB::table('relationships')->insert([
                        'relationship_id' => Str::uuid()->toString(),
                        'source_entity_id' => $entity->entity_id,
                        'target_entity_id' => $targetEntity->entity_id,
                        'relationship_type' => $hint['relationship_type'],
                        'confidence' => $hint['confidence'] ?? 'medium',
                        'created_by' => "pipeline:{$this->batchId}",
                        'created_at' => now(),
                    ]);
                    $created++;
                } catch (\Throwable) {
                    // Skip failed relationships silently
                }
            }

            // Clean up hints from attributes
            DB::table('entities')
                ->where('entity_id', $entity->entity_id)
                ->update([
                    'attributes' => DB::raw("attributes - '_relationship_hints'"),
                ]);
        }

        Log::info("[Pipeline] Created {$created} relationships from embedded hints");
    }

    /**
     * Check if a relationship already exists (either direction for symmetric types).
     */
    private function relationshipExists(string $sourceId, string $targetId, string $type): bool
    {
        $exists = DB::table('relationships')
            ->where('source_entity_id', $sourceId)
            ->where('target_entity_id', $targetId)
            ->where('relationship_type', $type)
            ->exists();

        if ($exists) {
            return true;
        }

        // Check reverse direction for symmetric types
        $symmetricTypes = [
            'married_to', 'allied_with', 'sibling_of',
            'trades_with', 'at_war_with',
        ];

        if (in_array($type, $symmetricTypes, true)) {
            return DB::table('relationships')
                ->where('source_entity_id', $targetId)
                ->where('target_entity_id', $sourceId)
                ->where('relationship_type', $type)
                ->exists();
        }

        return false;
    }
}
